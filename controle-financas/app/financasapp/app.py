"""App Android do Controle de Finanças (Toga / BeeWare).

Reaproveita o pacote `financas` do PC: o celular sincroniza sozinho com a
Pluggy e guarda tudo num SQLite dentro da área privada do app.
Abas: Resumo · Gastos · Investimentos · Patrimônio · Ajustes.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

from financas.db import Banco
from financasapp import configuracao, dados

VERDE = "#2e7d32"
VERMELHO = "#c62828"
CINZA = "#757575"
TODAS = "Todas as categorias"


def rotulo(texto: str, tamanho: int | None = None, negrito: bool = False,
           cor: str | None = None, flex: int | None = None, direita: bool = False,
           margem=None) -> toga.Label:
    estilo = {}
    if tamanho:
        estilo["font_size"] = tamanho
    if negrito:
        estilo["font_weight"] = "bold"
    if cor:
        estilo["color"] = cor
    if flex:
        estilo["flex"] = flex
    if direita:
        estilo["text_align"] = "right"
    if margem is not None:
        estilo["margin"] = margem
    return toga.Label(texto, style=Pack(**estilo))


def linha(*filhos, margem=(2, 0)) -> toga.Box:
    return toga.Box(children=list(filhos), style=Pack(direction=ROW, margin=margem))


def coluna(filhos, margem=12) -> toga.Box:
    return toga.Box(children=list(filhos), style=Pack(direction=COLUMN, margin=margem))


def titulo_secao(texto: str) -> toga.Label:
    return rotulo(texto, tamanho=15, negrito=True, margem=(14, 0, 4, 0))


def encurtar(texto: str, maximo: int = 34) -> str:
    return texto if len(texto) <= maximo else texto[: maximo - 1] + "…"


class FinancasApp(toga.App):
    # ------------------------------------------------------------ início
    def startup(self):
        pasta_extra = os.environ.get("FINANCAS_APP_DIR")  # usado em testes/dev
        pasta_dados = Path(pasta_extra or self.paths.data)
        pasta_dados.mkdir(parents=True, exist_ok=True)
        self.db_path = str(pasta_dados / "financas.db")
        self.config_path = Path(pasta_extra or self.paths.config) / "config.json"
        self.cfg = configuracao.carregar(self.config_path)

        meses = dados.ultimos_meses(date.today())
        self.mes_por_rotulo = {dados.rotulo_mes(m): m for m in meses}
        self.mes_resumo = meses[0]
        self.mes_gastos = meses[0]
        self.categoria_gastos: str | None = None

        self.areas = {nome: toga.ScrollContainer(horizontal=False, style=Pack(flex=1))
                      for nome in ("resumo", "gastos", "investimentos", "patrimonio",
                                   "ajustes")}

        abas = toga.OptionContainer(
            content=[
                ("Resumo", self._aba_resumo()),
                ("Gastos", self._aba_gastos()),
                ("Invest.", toga.Box(children=[self.areas["investimentos"]],
                                     style=Pack(direction=COLUMN, flex=1))),
                ("Patrimônio", toga.Box(children=[self.areas["patrimonio"]],
                                        style=Pack(direction=COLUMN, flex=1))),
                ("Ajustes", toga.Box(children=[self.areas["ajustes"]],
                                     style=Pack(direction=COLUMN, flex=1))),
            ],
            style=Pack(flex=1),
        )
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = abas
        self.atualizar_tudo()
        self.main_window.show()

    @contextmanager
    def banco(self):
        b = Banco(self.db_path)
        try:
            yield b
        finally:
            b.fechar()

    def _habilitar_sync(self, ligado: bool) -> None:
        for botao in (self.botao_sync_resumo, getattr(self, "botao_sync_ajustes", None)):
            if botao is not None:
                botao.enabled = ligado

    def atualizar_tudo(self) -> None:
        self.render_resumo()
        self.render_gastos()
        self.render_investimentos()
        self.render_patrimonio()
        self.render_ajustes()

    # ------------------------------------------------------------ resumo
    def _aba_resumo(self) -> toga.Box:
        self.sel_mes_resumo = toga.Selection(items=list(self.mes_por_rotulo),
                                             on_change=self._mudou_mes_resumo,
                                             style=Pack(flex=1))
        self.status = rotulo("", tamanho=12, cor=CINZA, margem=(0, 12))
        self.botao_sync_resumo = toga.Button("Sincronizar", on_press=self.sincronizar)
        topo = linha(self.sel_mes_resumo, self.botao_sync_resumo, margem=(8, 12, 4, 12))
        return toga.Box(children=[topo, self.status, self.areas["resumo"]],
                        style=Pack(direction=COLUMN, flex=1))

    def _mudou_mes_resumo(self, widget, **kwargs):
        self.mes_resumo = self.mes_por_rotulo.get(widget.value, self.mes_resumo)
        self.render_resumo()

    def render_resumo(self) -> None:
        with self.banco() as b:
            d = dados.tela_resumo(b, self.mes_resumo)
        filhos = []
        if d["sem_dados"]:
            filhos.append(rotulo("Nenhum dado ainda.", tamanho=16, negrito=True))
            filhos.append(rotulo("Abra a aba Ajustes, preencha as chaves da Pluggy e "
                                 "toque em Sincronizar."))
            self.areas["resumo"].content = coluna(filhos)
            return
        filhos += [
            linha(rotulo("Receitas", flex=1), rotulo(d["receitas"], tamanho=16, cor=VERDE)),
            linha(rotulo("Gastos", flex=1), rotulo(d["gastos"], tamanho=16, cor=VERMELHO)),
            linha(rotulo("Saldo do mês", negrito=True, flex=1),
                  rotulo(d["saldo"], tamanho=20, negrito=True,
                         cor=VERDE if d["saldo_positivo"] else VERMELHO)),
            rotulo(f"{d['quantidade']} gasto(s) em {d['rotulo']}", tamanho=12, cor=CINZA),
        ]
        if d["categorias"]:
            filhos.append(titulo_secao("Gastos por categoria"))
        for c in d["categorias"]:
            filhos.append(linha(rotulo(c["nome"], flex=1), rotulo(c["valor"]),
                                margem=(6, 0, 0, 0)))
            filhos.append(toga.ProgressBar(max=100, value=min(c["pct"], 100)))
            info = f"{c['pct']:.1f}% dos gastos"
            if c["orcamento"]:
                info += f" · orçamento {c['orcamento']} ({c['uso_orcamento']:.0f}%)"
                if c["estourou"]:
                    info += " · ESTOUROU"
            filhos.append(rotulo(info, tamanho=11,
                                 cor=VERMELHO if c["estourou"] else CINZA))
        if d["fora_do_total"]:
            filhos.append(titulo_secao("Fora do total"))
            filhos.append(rotulo("Só mudam o dinheiro de lugar (fatura, contas suas, "
                                 "investimentos).", tamanho=11, cor=CINZA))
            for f in d["fora_do_total"]:
                filhos.append(rotulo(f["nome"], negrito=True, margem=(6, 0, 0, 0)))
                filhos.append(linha(rotulo(f"entrou {f['entrou']}", cor=VERDE, flex=1),
                                    rotulo(f"saiu {f['saiu']}", cor=VERMELHO)))
        self.areas["resumo"].content = coluna(filhos)

    # ------------------------------------------------------------ gastos
    def _aba_gastos(self) -> toga.Box:
        self.sel_mes_gastos = toga.Selection(items=list(self.mes_por_rotulo),
                                             on_change=self._mudou_filtro_gastos,
                                             style=Pack(flex=1))
        self.sel_cat_gastos = toga.Selection(items=[TODAS],
                                             on_change=self._mudou_filtro_gastos,
                                             style=Pack(flex=1))
        topo = coluna([self.sel_mes_gastos, self.sel_cat_gastos], margem=(8, 12, 4, 12))
        return toga.Box(children=[topo, self.areas["gastos"]],
                        style=Pack(direction=COLUMN, flex=1))

    def _mudou_filtro_gastos(self, widget, **kwargs):
        if getattr(self, "_ajustando_filtros", False):
            return
        self.mes_gastos = self.mes_por_rotulo.get(self.sel_mes_gastos.value, self.mes_gastos)
        cat = self.sel_cat_gastos.value
        self.categoria_gastos = None if cat in (None, TODAS) else cat
        self.render_gastos()

    def render_gastos(self) -> None:
        with self.banco() as b:
            d = dados.tela_gastos(b, self.mes_gastos, self.categoria_gastos)
        # atualiza a lista de categorias sem disparar o filtro de novo
        opcoes = [TODAS] + d["categorias"]
        if list(self.sel_cat_gastos.items) != opcoes:
            self._ajustando_filtros = True
            try:
                atual = self.categoria_gastos if self.categoria_gastos in opcoes else TODAS
                self.sel_cat_gastos.items = opcoes
                self.sel_cat_gastos.value = atual
            finally:
                self._ajustando_filtros = False
        filhos = [linha(rotulo(f"{d['quantidade']} lançamento(s)", cor=CINZA, flex=1),
                        rotulo(f"total {d['total']}", negrito=True))]
        if not d["itens"]:
            filhos.append(rotulo("Nada neste mês.", margem=(12, 0)))
        for t in d["itens"]:
            filhos.append(linha(rotulo(encurtar(t["descricao"]), flex=1),
                                rotulo(t["valor"], negrito=True,
                                       cor=VERDE if t["entrada"] else VERMELHO),
                                margem=(8, 0, 0, 0)))
            filhos.append(rotulo(f"{t['data']} · {t['categoria']} · {t['conta']}",
                                 tamanho=11, cor=CINZA))
        if d["cortado"]:
            filhos.append(rotulo("Mostrando só os mais recentes. Filtre por categoria "
                                 "para ver o resto.", tamanho=11, cor=CINZA, margem=(10, 0)))
        self.areas["gastos"].content = coluna(filhos)

    # ------------------------------------------------------- investimentos
    def render_investimentos(self) -> None:
        with self.banco() as b:
            d = dados.tela_investimentos(b)
        if not d["grupos"]:
            self.areas["investimentos"].content = coluna(
                [rotulo("Nenhum investimento ainda. Sincronize na aba Ajustes.")])
            return
        filhos = [rotulo("Total investido", cor=CINZA),
                  rotulo(d["total"], tamanho=22, negrito=True)]
        if d["rendimento"]:
            filhos.append(rotulo(f"Rendimento (onde o banco informa o valor aplicado): "
                                 f"{d['rendimento']}", tamanho=12, cor=CINZA))
        for g in d["grupos"]:
            filhos.append(titulo_secao(f"{g['nome']} · {g['total']} ({g['pct']:.1f}%)"))
            filhos.append(toga.ProgressBar(max=100, value=min(g["pct"], 100)))
            for i in g["itens"]:
                filhos.append(linha(rotulo(encurtar(i["nome"]), flex=1),
                                    rotulo(i["valor"]), margem=(6, 0, 0, 0)))
                if i["detalhes"]:
                    filhos.append(rotulo(i["detalhes"], tamanho=11, cor=CINZA))
        self.areas["investimentos"].content = coluna(filhos)

    # ---------------------------------------------------------- patrimônio
    def render_patrimonio(self) -> None:
        with self.banco() as b:
            d = dados.tela_patrimonio(b)
        filhos = [
            rotulo("Patrimônio líquido", cor=CINZA),
            rotulo(d["liquido"], tamanho=24, negrito=True,
                   cor=VERDE if d["liquido_positivo"] else VERMELHO),
            linha(rotulo("Contas", flex=1), rotulo(d["contas"]), margem=(10, 0, 0, 0)),
            linha(rotulo("Investimentos", flex=1), rotulo(d["investimentos"])),
            linha(rotulo("Faturas de cartão", flex=1), rotulo(d["faturas"], cor=VERMELHO)),
        ]
        if d["lista_contas"]:
            filhos.append(titulo_secao("Contas e cartões"))
            for c in d["lista_contas"]:
                filhos.append(linha(rotulo(encurtar(f"{c['nome']} ({c['tipo']})", 30), flex=1),
                                    rotulo(c["saldo"])))
        if len(d["evolucao"]) > 1:
            filhos.append(titulo_secao("Evolução dos investimentos"))
            for e in d["evolucao"]:
                extra = f"  ({e['variacao']})" if e["variacao"] else ""
                filhos.append(linha(rotulo(e["mes"], flex=1), rotulo(e["total"] + extra)))
        if d["ultima_sync"]:
            filhos.append(rotulo(f"Última sincronização: {d['ultima_sync']}", tamanho=11,
                                 cor=CINZA, margem=(14, 0, 0, 0)))
        self.areas["patrimonio"].content = coluna(filhos)

    # ------------------------------------------------------------- ajustes
    def render_ajustes(self) -> None:
        self.in_client_id = toga.TextInput(value=self.cfg.client_id,
                                           placeholder="Client ID")
        self.in_client_secret = toga.PasswordInput(value=self.cfg.client_secret,
                                                   placeholder="Client Secret")
        self.in_item_ids = toga.MultilineTextInput(value="\n".join(self.cfg.item_ids),
                                                   placeholder="Um Item ID por linha",
                                                   style=Pack(height=110))
        self.status_ajustes = rotulo("", tamanho=12, cor=CINZA)
        filhos = [
            titulo_secao("Conexão com a Pluggy"),
            rotulo("Use as mesmas chaves do .env do PC. Elas ficam salvas só "
                   "neste celular.", tamanho=11, cor=CINZA),
            rotulo("Client ID", margem=(8, 0, 0, 0)), self.in_client_id,
            rotulo("Client Secret", margem=(8, 0, 0, 0)), self.in_client_secret,
            rotulo("Item IDs (um por linha)", margem=(8, 0, 0, 0)), self.in_item_ids,
            linha(toga.Button("Salvar", on_press=self.salvar_config, style=Pack(flex=1)),
                  margem=(8, 0, 0, 0)),
            self.status_ajustes,
            titulo_secao("Sincronização"),
            rotulo("A Pluggy atualiza os dados 1x por dia. A primeira vez baixa "
                   "12 meses e pode levar alguns minutos.", tamanho=11, cor=CINZA),
        ]
        self.botao_sync_ajustes = toga.Button("Sincronizar agora", on_press=self.sincronizar)
        filhos.append(self.botao_sync_ajustes)

        filhos.append(titulo_secao("Regras de categoria"))
        filhos.append(rotulo("Se a descrição contém o texto, vai para a categoria. "
                             "Vence a primeira regra da lista.", tamanho=11, cor=CINZA))
        with self.banco() as b:
            regras = dados.listar_regras(b)
        for r in regras:
            filhos.append(linha(
                rotulo(encurtar(f"'{r['padrao']}' → {r['categoria']}", 30), flex=1),
                toga.Button("Remover",
                            on_press=lambda w, rid=r["id"], **kw: self.remover_regra(rid)),
                margem=(4, 0)))
        self.in_regra_padrao = toga.TextInput(placeholder="Texto (ex.: ifood)")
        self.in_regra_categoria = toga.TextInput(placeholder="Categoria (ex.: Alimentação)")
        filhos += [self.in_regra_padrao, self.in_regra_categoria,
                   toga.Button("Adicionar regra", on_press=self.adicionar_regra)]
        self.areas["ajustes"].content = coluna(filhos)

    def salvar_config(self, widget, **kwargs):
        self.cfg = configuracao.ConfigApp(
            client_id=(self.in_client_id.value or "").strip(),
            client_secret=(self.in_client_secret.value or "").strip(),
            item_ids=configuracao.separar_ids(self.in_item_ids.value or ""),
            dias_iniciais=self.cfg.dias_iniciais,
        )
        configuracao.salvar(self.config_path, self.cfg)
        self.in_item_ids.value = "\n".join(self.cfg.item_ids)
        if self.cfg.completa:
            self.status_ajustes.text = (f"Salvo. {len(self.cfg.item_ids)} conexão(ões). "
                                        "Agora toque em Sincronizar.")
        else:
            self.status_ajustes.text = "Salvo, mas falta preencher algum campo."

    def adicionar_regra(self, widget, **kwargs):
        try:
            with self.banco() as b:
                n = dados.adicionar_regra(b, self.in_regra_padrao.value,
                                          self.in_regra_categoria.value)
        except ValueError as e:
            self.status_ajustes.text = str(e)
            return
        self.atualizar_tudo()
        self.status_ajustes.text = f"Regra salva ({n} lançamento(s) recategorizado(s))."

    def remover_regra(self, regra_id: int):
        with self.banco() as b:
            n = dados.remover_regra(b, regra_id)
        self.atualizar_tudo()
        self.status_ajustes.text = f"Regra removida ({n} lançamento(s) recategorizado(s))."

    # -------------------------------------------------------- sincronizar
    async def sincronizar(self, widget, **kwargs):
        if not self.cfg.completa:
            self.status.text = "Preencha e salve as chaves na aba Ajustes."
            self.status_ajustes.text = self.status.text
            return
        self._habilitar_sync(False)
        self.status.text = "Sincronizando… (a primeira vez pode levar alguns minutos)"
        self.status_ajustes.text = self.status.text
        try:
            mensagem = await asyncio.get_running_loop().run_in_executor(
                None, dados.sincronizar_pluggy, self.db_path, self.cfg.client_id,
                self.cfg.client_secret, self.cfg.item_ids, self.cfg.dias_iniciais)
        except Exception as e:  # rede, chave errada, ID errado…
            mensagem = f"Erro ao sincronizar: {str(e)[:300]}"
        finally:
            self._habilitar_sync(True)
        self.atualizar_tudo()
        self.status.text = mensagem
        self.status_ajustes.text = mensagem


def main():
    return FinancasApp()
