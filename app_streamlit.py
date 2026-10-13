"""
Interface web do trabalho, em Streamlit — roda no navegador, sem precisar de
um ambiente gráfico local.

Executa com:
    streamlit run app_streamlit.py

Toda a lógica de ambiente e busca é reaproveitada de `mapa.py` e `busca.py`;
esta camada só cuida de desenhar o mapa e a árvore de busca e de orquestrar a
interação (seleção de algoritmo, animação, comparação).
"""

from __future__ import annotations

import time

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from matplotlib.figure import Figure

from arvore import construir_figura
from busca import (ALGORITMOS, VALOR_RECOMPENSA, ResultadoBusca, executar_algoritmo,
                   executar_com_tempo_medio)
from mapa import Ambiente, PRESET_PADRAO, PRESETS_LABIRINTO, gerar_ambiente_preset

# O terreno usa uma única cor (roxo) que escurece conforme o custo sobe: quanto
# mais escuro, mais caro. Assim nenhuma célula se confunde com os marcadores
# (azul, verde, dourado, laranja e vermelho) nem com a parede, que é quase preta.
CORES_TERRENO = {
    '.': "#f3f0fa",
    ':': "#d4c7ea",
    '^': "#9b82c8",
    '~': "#5a3f94",
    '#': "#14151a",
}
NOMES_TERRENO = {
    '.': "Sólido e plano — custo 1",
    ':': "Arenoso — custo 4",
    '^': "Rochoso — custo 10",
    '~': "Pântano — custo 20",
}
DESCRICAO_ALGORITMO = {
    "Busca em Largura": "Explora por camadas (menos passos). Ignora o custo do terreno, "
                        "então acha o caminho mais curto, não o mais barato.",
    "Busca em Profundidade": "Segue um ramo até o fim antes de tentar outro. Acha "
                             "*um* caminho, sem garantia de ser curto ou barato.",
    "Busca Gulosa": "Expande sempre o que parece mais perto do prêmio, ignorando o "
                    "custo já gasto. Rápida, mas sem garantia de ser a melhor rota.",
    "A*": "Combina custo já gasto + estimativa até o prêmio. Só desvia para uma "
          "recompensa quando o desvio custa menos do que ela vale. Com a heurística "
          "admissível, acha a rota ótima.",
}
AJUDA_EXPANDIDOS = ("Quantos nós o algoritmo tirou da fronteira e examinou. Menos "
                    "expandidos = busca mais eficiente.")
AJUDA_TEMPO = "Tempo de execução do algoritmo (sem contar o desenho da tela)."
COR_FUNDO_MAPA = "#1e1f26"
COR_CAMINHO = "#ff8c42"
COR_INICIO = "#3a86ff"
COR_OBJETIVO = "#2ecc71"
COR_RECOMPENSA = "#f2c14e"
COR_AGENTE = "#e63946"

# Paleta categórica validada (contraste + daltonismo) para o comparativo entre
# algoritmos — mesma cor em todos os gráficos, sempre a mesma ordem.
CORES_ALGORITMO = {
    "Busca em Largura": "#2a78d6",
    "Busca em Profundidade": "#eb6834",
    "Busca Gulosa": "#1baf7a",
    "A*": "#eda100",
}


def limpar_resultados() -> None:
    """Descarta tudo o que foi calculado: vale quando o mapa ou o objetivo mudam."""
    st.session_state.resultado = None
    st.session_state.comparacao = None


def desenhar_mapa(ambiente: Ambiente, caminho: list[tuple[int, int]] | None = None,
                   agente_pos: tuple[int, int] | None = None,
                   recompensas_visiveis: list[tuple[int, int]] | None = None) -> Figure:
    largura = max(6.0, ambiente.colunas * 0.32)
    altura = max(4.0, ambiente.linhas * 0.32)
    fig, ax = plt.subplots(figsize=(largura, altura))
    fig.patch.set_facecolor(COR_FUNDO_MAPA)
    ax.set_facecolor(COR_FUNDO_MAPA)

    for r in range(ambiente.linhas):
        for c in range(ambiente.colunas):
            terreno = ambiente.grid[r][c]
            ax.add_patch(plt.Rectangle((c, r), 1, 1, facecolor=CORES_TERRENO[terreno],
                                        edgecolor="#14151a", linewidth=0.4))

    if caminho:
        for (r, c) in caminho:
            ax.add_patch(plt.Rectangle((c + 0.08, r + 0.08), 0.84, 0.84, fill=False,
                                        edgecolor=COR_CAMINHO, linewidth=2.4, zorder=3))

    recompensas = ambiente.recompensas if recompensas_visiveis is None else recompensas_visiveis
    for (r, c) in recompensas:
        ax.plot(c + 0.5, r + 0.5, marker="o", markersize=15, markerfacecolor=COR_RECOMPENSA,
                markeredgecolor="#8a6d1a", zorder=4)
        ax.text(c + 0.5, r + 0.5, "$", ha="center", va="center", fontsize=9,
                color="#4a3900", fontweight="bold", zorder=5)

    # Os rótulos têm fundo escuro para continuar legíveis sobre qualquer terreno.
    rotulo = dict(ha="center", va="bottom", fontsize=9, color="white", fontweight="bold",
                  zorder=7, bbox=dict(boxstyle="round,pad=0.15", fc=COR_FUNDO_MAPA,
                                      ec="none", alpha=0.85))

    ir, ic = ambiente.inicio
    ax.plot(ic + 0.5, ir + 0.5, marker="o", markersize=17, markerfacecolor=COR_INICIO,
            markeredgecolor="white", markeredgewidth=1.3, zorder=4)
    ax.text(ic + 0.5, ir - 0.2, "Início", **rotulo)

    gr, gc = ambiente.objetivo
    ax.plot(gc + 0.5, gr + 0.5, marker="*", markersize=24, markerfacecolor=COR_OBJETIVO,
            markeredgecolor="white", markeredgewidth=1.1, zorder=4)
    ax.text(gc + 0.5, gr - 0.2, "Prêmio", **rotulo)

    if agente_pos is not None:
        ar, ac = agente_pos
        ax.plot(ac + 0.5, ar + 0.5, marker="o", markersize=15, markerfacecolor=COR_AGENTE,
                markeredgecolor="white", markeredgewidth=1.4, zorder=6)

    ax.set_xlim(0, ambiente.colunas)
    ax.set_ylim(0, ambiente.linhas)
    ax.invert_yaxis()
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout(pad=0.3)
    return fig


def _item_legenda(simbolo_html: str, texto: str) -> str:
    # Sem `color` definido: o texto herda a cor do tema (claro ou escuro) do Streamlit.
    return (f'<span style="display:inline-flex;align-items:center;margin:0 24px 8px 0;'
            f'font-size:1rem;">{simbolo_html}<span style="margin-left:8px;">{texto}</span></span>')


def desenhar_legenda() -> None:
    """Legenda em duas linhas: o que cada cor de terreno custa e o que cada
    símbolo desenhado sobre o mapa significa."""
    borda = "border:1px solid rgba(128,128,128,0.8);"
    quadrado = lambda cor: (f'<span style="width:22px;height:22px;background:{cor};{borda}'
                            f'border-radius:3px;display:inline-block;"></span>')
    circulo = lambda cor, conteudo="": (
        f'<span style="width:22px;height:22px;background:{cor};{borda}border-radius:50%;'
        f'display:inline-flex;align-items:center;justify-content:center;font-weight:bold;'
        f'font-size:0.85rem;color:#4a3900;">{conteudo}</span>')

    terrenos = [_item_legenda(quadrado(CORES_TERRENO[t]), NOMES_TERRENO[t]) for t in ".:^~"]
    terrenos.append(_item_legenda(quadrado(CORES_TERRENO['#']), "Parede — intransponível"))
    elementos = [
        _item_legenda(circulo(COR_INICIO), "Início"),
        _item_legenda(f'<span style="color:{COR_OBJETIVO};font-size:1.7rem;line-height:1;">★</span>',
                      "Prêmio (objetivo)"),
        _item_legenda(circulo(COR_RECOMPENSA, "$"), "Recompensa"),
        _item_legenda(f'<span style="width:18px;height:18px;border:3px solid {COR_CAMINHO};'
                      f'border-radius:3px;display:inline-block;"></span>', "Caminho encontrado"),
        _item_legenda(circulo(COR_AGENTE), "Agente (na animação)"),
    ]
    st.markdown(
        '<div style="padding:6px 0 10px 0;">'
        '<div style="font-weight:600;margin-bottom:6px;">Terreno — quanto mais escuro, '
        'mais caro entrar na célula</div>'
        f'<div>{"".join(terrenos)}</div>'
        '<div style="font-weight:600;margin:8px 0 6px 0;">Elementos do mapa</div>'
        f'<div>{"".join(elementos)}</div></div>',
        unsafe_allow_html=True)


def animar_agente(ambiente: Ambiente, resultado: ResultadoBusca,
                   placeholder_mapa, placeholder_status) -> None:
    caminho = resultado.caminho
    recompensas_no_caminho = set(resultado.recompensas_coletadas)
    coletadas: set[tuple[int, int]] = set()
    custo = 0
    for i, pos in enumerate(caminho):
        if i > 0:
            custo += ambiente.custo_aresta(caminho[i - 1], pos)
        if pos in recompensas_no_caminho:
            coletadas.add(pos)
        recompensas_visiveis = [r for r in ambiente.recompensas if r not in coletadas]

        fig = desenhar_mapa(ambiente, caminho=caminho, agente_pos=pos,
                             recompensas_visiveis=recompensas_visiveis)
        placeholder_mapa.pyplot(fig, width="stretch")
        plt.close(fig)
        placeholder_status.markdown(
            f"**Passo {i + 1}/{len(caminho)}** · Custo acumulado: **{custo}** · "
            f"Recompensas coletadas: **{len(coletadas)}**")
        time.sleep(0.12)
    placeholder_status.markdown(
        f"✅ **Agente chegou ao objetivo!** Custo total: **{custo}** · "
        f"Recompensas coletadas: **{len(coletadas)}**")


def montar_tabela_comparacao(resultados: dict[str, ResultadoBusca], ambiente: Ambiente) -> pd.DataFrame:
    linhas = []
    for nome, r in resultados.items():
        linhas.append({
            "Algoritmo": nome,
            "Caminho encontrado": "Sim" if r.encontrou_caminho else "Não",
            "Custo total": r.custo_total if r.encontrou_caminho else None,
            "Recompensas": f"{len(r.recompensas_coletadas)}/{len(ambiente.recompensas)}"
                           if r.encontrou_caminho else "0",
            "Saldo": r.saldo if r.encontrou_caminho else None,
            "Nós expandidos": r.nos_expandidos,
            "Nós gerados": r.nos_gerados,
            "Pico da fronteira": r.max_fronteira,
            "Tempo médio (ms)": round(r.tempo_execucao_s * 1000, 3),
            "Execuções": r.repeticoes_tempo,
        })
    return pd.DataFrame(linhas).set_index("Algoritmo")


def grafico_comparativo(resultados: dict[str, ResultadoBusca], coluna: str, titulo: str, fmt: str):
    nomes = list(resultados.keys())
    valores = [getattr(resultados[n], coluna) if coluna != "tempo_ms" else
               resultados[n].tempo_execucao_s * 1000 for n in nomes]
    cores = [CORES_ALGORITMO[n] for n in nomes]

    fig, ax = plt.subplots(figsize=(4.3, 3.2))
    barras = ax.bar(nomes, valores, color=cores, width=0.6)
    ax.bar_label(barras, fmt=fmt, padding=3, fontsize=8, color="#222")
    ax.set_title(titulo, fontsize=10.5, color="#222")
    ax.set_xticks(range(len(nomes)))
    ax.set_xticklabels([n.replace("Busca em ", "").replace("Busca ", "") for n in nomes],
                        rotation=15, ha="right", fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#c3c2b7")
    ax.tick_params(colors="#52514e")
    fig.tight_layout()
    return fig


def main() -> None:
    st.set_page_config(page_title="Trabalho 1 — Busca em Grafo", layout="wide")

    if "ambiente" not in st.session_state:
        st.session_state.preset_atual = PRESET_PADRAO
        st.session_state.ambiente = gerar_ambiente_preset(PRESET_PADRAO)
        st.session_state.objetivo_padrao = st.session_state.ambiente.objetivo
        limpar_resultados()

    ambiente: Ambiente = st.session_state.ambiente
    # O slider fica na barra lateral (mais abaixo), mas o valor já está no
    # session_state quando o script roda de novo após mexer nele.
    valor = st.session_state.get("valor_recompensa", VALOR_RECOMPENSA)

    st.title("Navegação Autônoma por Busca em Grafo")
    st.caption("Fundamentos da Inteligência Artificial — Trabalho 1 (UTFPR) · "
               "Busca em Largura · Busca em Profundidade · Busca Gulosa · A*")

    with st.expander("Como funciona / como usar", expanded=True):
        st.markdown(
            f"O agente (azul) precisa chegar ao **prêmio** (estrela verde) atravessando um "
            f"labirinto. Cada célula tem um **custo** (terreno mais escuro = mais caro) e as "
            f"**recompensas ($)** valem **{valor}** pontos cada (ajustável no slider "
            f"*Valor da recompensa*).\n\n"
            f"1. Escolha o **formato do labirinto** e clique em *Gerar Mapa*.\n"
            f"2. Escolha um **algoritmo** e clique em *Calcular Rota*: o caminho aparece em "
            f"laranja e as métricas ao lado.\n"
            f"3. Veja a **árvore de busca** (o que o algoritmo explorou) e use *Comparar "
            f"Algoritmos* para ver os quatro lado a lado.\n\n"
            f"**Saldo = {valor} × recompensas coletadas − custo do percurso.** "
            f"Vale a pena desviar para uma recompensa só se o desvio custar menos que "
            f"{valor}.")

    with st.sidebar:
        st.header("Controles")

        st.subheader("Formato do labirinto")
        nome_preset = st.selectbox("Escolha o formato", list(PRESETS_LABIRINTO.keys()),
                                    index=list(PRESETS_LABIRINTO.keys()).index(
                                        st.session_state.preset_atual))
        if st.button("Gerar Mapa", width="stretch"):
            st.session_state.preset_atual = nome_preset
            st.session_state.ambiente = gerar_ambiente_preset(nome_preset)
            st.session_state.objetivo_padrao = st.session_state.ambiente.objetivo
            limpar_resultados()
            st.rerun()

        st.divider()
        st.subheader("Valor da recompensa")
        st.slider("Valor de cada $ (V)", 0, 100, VALOR_RECOMPENSA, key="valor_recompensa",
                  on_change=limpar_resultados,
                  help="O enunciado não define quanto vale uma recompensa; este é um "
                       "parâmetro de modelagem. Um desvio compensa quando custa menos que V. "
                       "Com V baixo o A* ignora as recompensas; com V alto ele as busca, "
                       "aceitando rotas mais caras. Buscas cegas não são afetadas (só o saldo).")

        st.divider()
        st.subheader("Algoritmo de busca")
        nome_algoritmo = st.selectbox("Algoritmo", list(ALGORITMOS.keys()), index=3,
                                       label_visibility="collapsed")
        st.caption(DESCRICAO_ALGORITMO[nome_algoritmo])

        if st.button("Calcular Rota", type="primary", width="stretch"):
            st.session_state.resultado = executar_algoritmo(nome_algoritmo, ambiente, valor)

        st.divider()
        st.subheader("Objetivo")
        st.caption(f"Objetivo atual: {ambiente.objetivo}")
        c1, c2 = st.columns(2)
        nova_linha = c1.number_input("Linha", 0, ambiente.linhas - 1, ambiente.objetivo[0])
        nova_coluna = c2.number_input("Coluna", 0, ambiente.colunas - 1, ambiente.objetivo[1])
        if st.button("Definir Novo Objetivo", width="stretch"):
            pos = (int(nova_linha), int(nova_coluna))
            if ambiente.eh_parede(pos):
                st.error("Essa célula é uma parede — escolha outra.")
            elif pos == ambiente.inicio:
                st.error("O objetivo não pode ser igual ao início.")
            else:
                ambiente.objetivo = pos
                limpar_resultados()
                st.rerun()
        if st.button("Restaurar Objetivo Padrão", width="stretch"):
            ambiente.objetivo = st.session_state.objetivo_padrao
            limpar_resultados()
            st.rerun()

        st.divider()
        if st.button("Comparar Algoritmos", width="stretch"):
            st.session_state.comparacao = {
                nome: executar_com_tempo_medio(
                    lambda a, nome=nome: executar_algoritmo(nome, a, valor), ambiente)
                for nome in ALGORITMOS}

    col_mapa, col_status = st.columns([2, 1], gap="large")

    with col_mapa:
        resultado = st.session_state.resultado
        caminho = resultado.caminho if (resultado and resultado.encontrou_caminho) else None
        placeholder_mapa = st.empty()
        fig = desenhar_mapa(ambiente, caminho=caminho)
        placeholder_mapa.pyplot(fig, width="stretch")
        plt.close(fig)
        desenhar_legenda()

        placeholder_status_animacao = st.empty()
        if resultado and resultado.encontrou_caminho:
            if st.button("Animar Agente"):
                animar_agente(ambiente, resultado, placeholder_mapa, placeholder_status_animacao)

    with col_status:
        st.subheader("Status")
        if resultado is None:
            st.info("Escolha um algoritmo e clique em \"Calcular Rota\".")
        else:
            st.success(f"[{resultado.nome}] Caminho encontrado!")
            m1, m2 = st.columns(2)
            m1.metric("Custo total", resultado.custo_total,
                      help="Soma dos custos dos terrenos pisados ao longo do caminho.")
            m2.metric("Recompensas", f"{len(resultado.recompensas_coletadas)}/{len(ambiente.recompensas)}",
                      help="Quantas recompensas ($) o caminho coletou, do total do mapa.")
            m3, m4 = st.columns(2)
            m3.metric("Saldo", resultado.saldo,
                      help=f"{resultado.valor_recompensa} × recompensas coletadas − custo total. "
                           "Quanto maior, melhor.")
            m4.metric("Nós expandidos", resultado.nos_expandidos, help=AJUDA_EXPANDIDOS)
            m5, m6 = st.columns(2)
            m5.metric("Pico da fronteira", resultado.max_fronteira,
                      help="Maior número de nós esperando para serem expandidos ao mesmo "
                           "tempo. Indica o uso de memória do algoritmo.")
            m6.metric("Tempo", f"{resultado.tempo_execucao_s * 1000:.2f} ms", help=AJUDA_TEMPO)
        st.caption("Passe o mouse sobre o **?** de cada métrica para ver o que ela significa.")

    st.divider()
    aba_arvore, aba_comparacao = st.tabs(["Árvore de Busca", "Comparação entre Algoritmos"])

    with aba_arvore:
        if resultado is None:
            st.info("Calcule uma rota primeiro para ver a árvore de busca gerada por ela.")
        else:
            fig_arvore = construir_figura(resultado)
            st.pyplot(fig_arvore, width="stretch")
            plt.close(fig_arvore)
            st.caption("Cada ponto é um estado que o algoritmo gerou; a raiz (topo) é o início "
                       "e cada linha liga um estado ao que o originou. "
                       "Azul = início · Verde = objetivo · Amarelo = recompensa · "
                       "Laranja = caminho escolhido · Cinza = explorado e descartado. "
                       "Árvore larga = muita exploração; árvore estreita = busca direta.")

    with aba_comparacao:
        comparacao = st.session_state.comparacao
        if comparacao is None:
            st.info("Clique em \"Comparar Algoritmos\" na barra lateral.")
        else:
            st.dataframe(montar_tabela_comparacao(comparacao, ambiente), width="stretch")
            st.caption(f"Saldo = {valor} × recompensas − custo do percurso. "
                       "Tempo = média de várias execuções. Pico da fronteira = maior "
                       "número de nós aguardando expansão ao mesmo tempo (memória).")
            graficos = [
                ("nos_expandidos", "Nós expandidos", "%d"),
                ("max_fronteira", "Pico da fronteira (memória)", "%d"),
                ("tempo_ms", "Tempo médio de execução (ms)", "%.2f"),
                ("saldo", "Saldo (maior é melhor)", "%d"),
            ]
            for linha in (graficos[:2], graficos[2:]):
                for coluna_st, (atributo, titulo, fmt) in zip(st.columns(2), linha):
                    with coluna_st:
                        fig = grafico_comparativo(comparacao, atributo, titulo, fmt)
                        st.pyplot(fig, width="stretch")
                        plt.close(fig)


if __name__ == "__main__":
    main()
