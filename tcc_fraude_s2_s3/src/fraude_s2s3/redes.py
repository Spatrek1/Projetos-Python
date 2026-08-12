"""Redes neurais para detecção de atipicidade contábil em S2/S3.

Três arquiteturas, em ordem crescente de exigência sobre os dados:

``AutoencoderTabular``
    Autoencoder denoising sobre o vetor (instituição, trimestre). O escore é o
    erro de reconstrução: a rede aprende a "variedade de normalidade" do
    conjunto e erra mais onde a observação não pertence a ela. É a única das
    três que **não precisa de rótulo** — e, como não existe rótulo público de
    fraude bancária no Brasil, é a espinha dorsal do trabalho.

``AutoencoderSequencial``
    GRU que lê ``janela`` trimestres e prevê o seguinte. O escore é o erro de
    previsão: mede **quebra estrutural** na trajetória da instituição, que é
    mais próximo da intuição de auditoria ("mudou de comportamento") do que a
    atipicidade transversal.

``RedeHibrida``
    Codificador compartilhado com duas cabeças: reconstrução (não
    supervisionada) e classificação sobre rótulo fraco. Só deve ser usada com
    :class:`fraude_s2s3.vazamento.GuardaCircularidade` ativa.

Nota sobre porte
----------------
S2+S3 tem ordem de 10^1–10^2 instituições e 24 trimestres. É pouco para rede
neural. A capacidade aqui é pequena de propósito, o treino usa parada
antecipada e o escore final é a **mediana sobre sementes**, para que o
resultado não dependa de uma inicialização feliz. Se o autoencoder não superar
PCA e Mahalanobis (ver :mod:`fraude_s2s3.baselines`), isso é resultado — e
deve ser reportado como tal.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_DISPONIVEL = True
except ImportError:  # pragma: no cover
    TORCH_DISPONIVEL = False

from . import diagnostico
from .config import CONFIG, ConfigRede

AREA = "modelagem/rede"


def _exigir_torch() -> None:
    if not TORCH_DISPONIVEL:
        diagnostico.registrar(
            area=AREA,
            item="PyTorch nao instalado no ambiente.",
            impacto="Nenhuma das redes pode ser treinada; restam apenas os baselines.",
            acao="pip install torch (CPU basta para este porte de painel).",
            severidade=diagnostico.Severidade.BLOQUEIA,
        )
        raise ImportError("PyTorch ausente: 'pip install torch'.")


# ---------------------------------------------------------------------------
# Arquiteturas
# ---------------------------------------------------------------------------

if TORCH_DISPONIVEL:

    class AutoencoderTabular(nn.Module):
        """Autoencoder denoising simétrico com gargalo estreito."""

        def __init__(self, n_entrada: int, cfg: ConfigRede):
            super().__init__()
            dims = [n_entrada, *cfg.dims_encoder, cfg.dim_latente]

            camadas: list[nn.Module] = []
            for a, b in zip(dims[:-1], dims[1:]):
                camadas += [nn.Linear(a, b), nn.LayerNorm(b), nn.GELU(), nn.Dropout(cfg.dropout)]
            self.encoder = nn.Sequential(*camadas[:-1])  # sem dropout no espaço latente

            # Decodificador espelhado, com a última camada linear "nua": a saída
            # reconstrói valores normalizados, que são reais e podem ser negativos.
            dims_inv = dims[::-1]
            camadas = []
            for a, b in zip(dims_inv[:-2], dims_inv[1:-1]):
                camadas += [nn.Linear(a, b), nn.LayerNorm(b), nn.GELU(), nn.Dropout(cfg.dropout)]
            camadas.append(nn.Linear(dims_inv[-2], dims_inv[-1]))
            self.decoder = nn.Sequential(*camadas)

        def forward(self, x):
            z = self.encoder(x)
            return self.decoder(z), z

    class AutoencoderSequencial(nn.Module):
        """GRU que prevê o trimestre seguinte a partir da janela anterior."""

        def __init__(self, n_atributos: int, cfg: ConfigRede):
            super().__init__()
            self.gru = nn.GRU(
                input_size=n_atributos, hidden_size=cfg.dim_oculta_gru,
                num_layers=cfg.camadas_gru, batch_first=True,
                dropout=cfg.dropout if cfg.camadas_gru > 1 else 0.0,
            )
            self.saida = nn.Sequential(
                nn.LayerNorm(cfg.dim_oculta_gru),
                nn.Dropout(cfg.dropout),
                nn.Linear(cfg.dim_oculta_gru, n_atributos),
            )

        def forward(self, x):
            h, _ = self.gru(x)
            return self.saida(h[:, -1, :])

    class RedeHibrida(nn.Module):
        """Codificador compartilhado; cabeças de reconstrução e classificação."""

        def __init__(self, n_entrada: int, cfg: ConfigRede):
            super().__init__()
            self.base = AutoencoderTabular(n_entrada, cfg)
            self.classificador = nn.Sequential(
                nn.Linear(cfg.dim_latente, 16), nn.GELU(),
                nn.Dropout(cfg.dropout), nn.Linear(16, 1),
            )

        def forward(self, x):
            recon, z = self.base(x)
            return recon, self.classificador(z).squeeze(-1), z


# ---------------------------------------------------------------------------
# Treino
# ---------------------------------------------------------------------------

@dataclass
class ResultadoTreino:
    escores: np.ndarray                 # erro por observação (mediana entre sementes)
    escores_por_semente: np.ndarray     # (sementes, n)
    erro_por_atributo: np.ndarray       # (n, atributos) — base da interpretação
    perda_treino: list[float]
    perda_validacao: list[float]
    epocas_efetivas: list[int]

    @property
    def estabilidade(self) -> float:
        """Correlação de posto média entre pares de sementes.

        Abaixo de ~0,8 o ranking depende mais da inicialização do que dos
        dados, e nenhuma instituição individual deve ser apontada.
        """
        import itertools

        from scipy.stats import spearmanr

        s = self.escores_por_semente
        if s.shape[0] < 2:
            return float("nan")
        rhos = [
            spearmanr(s[i], s[j]).statistic
            for i, j in itertools.combinations(range(s.shape[0]), 2)
        ]
        return float(np.nanmean(rhos))


def treinar_autoencoder(X_treino: np.ndarray, X_validacao: np.ndarray,
                        X_pontuar: np.ndarray, cfg: ConfigRede | None = None,
                        verboso: bool = False) -> ResultadoTreino:
    """Treina o autoencoder denoising e pontua ``X_pontuar``.

    Reamostragem entre sementes: cada semente reinicializa pesos e reembaralha
    lotes; o escore reportado é a mediana, e a dispersão entre sementes vira
    métrica de confiabilidade (:attr:`ResultadoTreino.estabilidade`).
    """
    _exigir_torch()
    cfg = cfg or CONFIG.rede
    n_atributos = X_treino.shape[1]

    escores_sementes, erros_atributo = [], []
    perdas_tr, perdas_va, epocas = [], [], []

    for semente in cfg.sementes:
        torch.manual_seed(semente)
        np.random.seed(semente)

        modelo = AutoencoderTabular(n_atributos, cfg)
        otimizador = torch.optim.AdamW(
            modelo.parameters(), lr=cfg.taxa_aprendizado, weight_decay=cfg.weight_decay
        )
        criterio = nn.MSELoss()

        t_tr = torch.tensor(X_treino, dtype=torch.float32)
        t_va = torch.tensor(X_validacao, dtype=torch.float32)
        carregador = DataLoader(TensorDataset(t_tr), batch_size=cfg.lote, shuffle=True)

        melhor, paciencia, melhores_pesos, epoca_melhor = float("inf"), 0, None, 0
        hist_tr, hist_va = [], []

        for epoca in range(cfg.epocas):
            modelo.train()
            soma = 0.0
            for (lote,) in carregador:
                ruido = lote + cfg.ruido_denoising * torch.randn_like(lote)
                recon, _ = modelo(ruido)
                perda = criterio(recon, lote)          # alvo é o vetor limpo
                otimizador.zero_grad()
                perda.backward()
                torch.nn.utils.clip_grad_norm_(modelo.parameters(), 1.0)
                otimizador.step()
                soma += perda.item() * len(lote)
            hist_tr.append(soma / max(len(t_tr), 1))

            modelo.eval()
            with torch.no_grad():
                recon_va, _ = modelo(t_va)
                perda_va = criterio(recon_va, t_va).item() if len(t_va) else float("nan")
            hist_va.append(perda_va)

            referencia = perda_va if len(t_va) else hist_tr[-1]
            if referencia < melhor - 1e-6:
                melhor, paciencia, epoca_melhor = referencia, 0, epoca
                melhores_pesos = {k: v.clone() for k, v in modelo.state_dict().items()}
            else:
                paciencia += 1
                if paciencia >= cfg.paciencia:
                    break

        if melhores_pesos is not None:
            modelo.load_state_dict(melhores_pesos)

        modelo.eval()
        with torch.no_grad():
            t_pt = torch.tensor(X_pontuar, dtype=torch.float32)
            recon, _ = modelo(t_pt)
            erro = (recon - t_pt) ** 2
        escores_sementes.append(erro.mean(dim=1).numpy())
        erros_atributo.append(erro.numpy())
        perdas_tr.append(hist_tr[-1] if hist_tr else float("nan"))
        perdas_va.append(melhor)
        epocas.append(epoca_melhor + 1)

        if verboso:
            print(f"  semente {semente}: {epoca_melhor + 1} epocas, perda_val={melhor:.5f}")

    escores_por_semente = np.vstack(escores_sementes)
    resultado = ResultadoTreino(
        escores=np.median(escores_por_semente, axis=0),
        escores_por_semente=escores_por_semente,
        erro_por_atributo=np.median(np.stack(erros_atributo), axis=0),
        perda_treino=perdas_tr, perda_validacao=perdas_va, epocas_efetivas=epocas,
    )
    _diagnosticar_treino(resultado, X_treino, n_atributos, cfg)
    return resultado


def treinar_sequencial(X_treino: np.ndarray, y_treino: np.ndarray,
                       X_validacao: np.ndarray, y_validacao: np.ndarray,
                       X_pontuar: np.ndarray, y_pontuar: np.ndarray,
                       cfg: ConfigRede | None = None) -> ResultadoTreino:
    """Treina o GRU de previsão e pontua pelo erro de previsão."""
    _exigir_torch()
    cfg = cfg or CONFIG.rede
    if X_treino.size == 0:
        raise ValueError("Sem sequencias de treino: ver painel.sequencias().")
    n_atributos = X_treino.shape[2]

    escores_sementes, erros_atributo, perdas_tr, perdas_va, epocas = [], [], [], [], []

    for semente in cfg.sementes:
        torch.manual_seed(semente)
        modelo = AutoencoderSequencial(n_atributos, cfg)
        otimizador = torch.optim.AdamW(
            modelo.parameters(), lr=cfg.taxa_aprendizado, weight_decay=cfg.weight_decay
        )
        criterio = nn.MSELoss()

        t_x = torch.tensor(X_treino, dtype=torch.float32)
        t_y = torch.tensor(y_treino, dtype=torch.float32)
        carregador = DataLoader(TensorDataset(t_x, t_y), batch_size=cfg.lote, shuffle=True)
        v_x = torch.tensor(X_validacao, dtype=torch.float32)
        v_y = torch.tensor(y_validacao, dtype=torch.float32)

        melhor, paciencia, pesos, epoca_melhor = float("inf"), 0, None, 0
        hist_tr = []
        for epoca in range(cfg.epocas):
            modelo.train()
            soma = 0.0
            for xb, yb in carregador:
                pred = modelo(xb)
                perda = criterio(pred, yb)
                otimizador.zero_grad()
                perda.backward()
                torch.nn.utils.clip_grad_norm_(modelo.parameters(), 1.0)
                otimizador.step()
                soma += perda.item() * len(xb)
            hist_tr.append(soma / max(len(t_x), 1))

            modelo.eval()
            with torch.no_grad():
                perda_va = criterio(modelo(v_x), v_y).item() if len(v_x) else hist_tr[-1]
            if perda_va < melhor - 1e-6:
                melhor, paciencia, epoca_melhor = perda_va, 0, epoca
                pesos = {k: v.clone() for k, v in modelo.state_dict().items()}
            else:
                paciencia += 1
                if paciencia >= cfg.paciencia:
                    break

        if pesos is not None:
            modelo.load_state_dict(pesos)
        modelo.eval()
        with torch.no_grad():
            pred = modelo(torch.tensor(X_pontuar, dtype=torch.float32))
            erro = (pred - torch.tensor(y_pontuar, dtype=torch.float32)) ** 2
        escores_sementes.append(erro.mean(dim=1).numpy())
        erros_atributo.append(erro.numpy())
        perdas_tr.append(hist_tr[-1] if hist_tr else float("nan"))
        perdas_va.append(melhor)
        epocas.append(epoca_melhor + 1)

    s = np.vstack(escores_sementes)
    return ResultadoTreino(
        escores=np.median(s, axis=0), escores_por_semente=s,
        erro_por_atributo=np.median(np.stack(erros_atributo), axis=0),
        perda_treino=perdas_tr, perda_validacao=perdas_va, epocas_efetivas=epocas,
    )


def _diagnosticar_treino(res: ResultadoTreino, X_treino: np.ndarray,
                         n_atributos: int, cfg: ConfigRede) -> None:
    """Verificações que decidem se o resultado pode ser reportado."""
    n = len(X_treino)
    n_parametros = 2 * sum(
        a * b for a, b in zip([n_atributos, *cfg.dims_encoder],
                              [*cfg.dims_encoder, cfg.dim_latente])
    )
    if n_parametros > n:
        diagnostico.registrar(
            area=AREA,
            item=(
                f"Rede com ~{n_parametros:,} parametros treinada em {n:,} observacoes "
                f"({n_parametros / max(n, 1):.0f}x mais parametros que dados)."
            ),
            impacto=(
                "Regime de sobreparametrizacao. O autoencoder pode reconstruir bem "
                "tambem as observacoes atipicas, achatando o escore e reduzindo o poder "
                "de deteccao. E a limitacao estrutural de aplicar rede neural a um "
                "painel do porte de S2+S3."
            ),
            acao=(
                "Reduzir ConfigRede.dims_encoder/dim_latente ate a razao ficar proxima "
                "de 1, e reportar no TCC a curva de sensibilidade do resultado a essa "
                "escolha. Alternativa: ativar Config.pretreino_fora_do_escopo para "
                "aprender a normalidade em S4/S5 e pontuar apenas S2/S3 — decisao que "
                "precisa de aval do orientador por alterar o escopo declarado."
            ),
            severidade=diagnostico.Severidade.COMPROMETE,
        )

    try:
        est = res.estabilidade
    except Exception:
        est = float("nan")
    if np.isfinite(est) and est < 0.80:
        diagnostico.registrar(
            area=AREA,
            item=f"Estabilidade entre sementes baixa (Spearman medio = {est:.2f}).",
            impacto=(
                "O ordenamento das instituicoes muda conforme a inicializacao. Nenhuma "
                "instituicao especifica pode ser apontada como atipica; no maximo cabe "
                "leitura agregada."
            ),
            acao=(
                "Aumentar ConfigRede.sementes, reduzir capacidade, ou concluir que o "
                "painel nao sustenta ranking individual — e dize-lo no TCC. "
                "Area: redes.treinar_autoencoder()."
            ),
            severidade=diagnostico.Severidade.COMPROMETE,
        )
