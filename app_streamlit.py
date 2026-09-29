"""
Segunda opção de interface para o mesmo trabalho, agora em Streamlit — útil
para apresentar pelo navegador (sem precisar de um ambiente gráfico local) ou
como alternativa à versão em Tkinter (`main.py`).

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
from busca import ALGORITMOS, VALOR_RECOMPENSA, ResultadoBusca, executar_com_tempo_medio
from mapa import Ambiente, PRESET_PADRAO, PRESETS_LABIRINTO, gerar_ambiente_preset

CORES_TERRENO = {
    '.': "#e7e7e3",
    ':': "#d9b56c",
    '^': "#7c7c7c",
    '~': "#3f5c43",
    '#': "#17181d",
}
NOMES_TERRENO = {
    '.': "Sólido e plano (custo 1)",
    ':': "Arenoso (custo 4)",
    '^': "Rochoso (custo 10)",
    '~': "Pântano (custo 20)",
}
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
    "Custo Uniforme": "#8e6ccf",
}


def encontrar_celula_isolada(ambiente: Ambiente) -> tuple[int, int] | None:
    """Acha uma célula andável inalcançável a partir do início (por exemplo,
    a sala isolada do mapa) — usada só para sugerir uma coordenada de teste
    na interface, então funciona com qualquer formato de labirinto."""
    visitados = {ambiente.inicio}
    fila = [ambiente.inicio]
    i = 0
    while i < len(fila):
        atual = fila[i]
        i += 1
        for viz in ambiente.vizinhos(atual):
            if viz not in visitados:
                visitados.add(viz)
                fila.append(viz)
    for r in range(ambiente.linhas):
        for c in range(ambiente.colunas):
            if not ambiente.eh_parede((r, c)) and (r, c) not in visitados:
                return (r, c)
    return None


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
                                        edgecolor=COR_CAMINHO, linewidth=1.8, zorder=3))

    recompensas = ambiente.recompensas if recompensas_visiveis is None else recompensas_visiveis
    for (r, c) in recompensas:
        ax.plot(c + 0.5, r + 0.5, marker="o", markersize=13, markerfacecolor=COR_RECOMPENSA,
                markeredgecolor="#8a6d1a", zorder=4)
        ax.text(c + 0.5, r + 0.5, "$", ha="center", va="center", fontsize=8,
                color="#4a3900", fontweight="bold", zorder=5)

    ir, ic = ambiente.inicio
    ax.plot(ic + 0.5, ir + 0.5, marker="o", markersize=16, markerfacecolor=COR_INICIO,
            markeredgecolor="white", markeredgewidth=1.3, zorder=4)
    ax.text(ic + 0.5, ir - 0.15, "Início", ha="center", va="bottom", fontsize=7.5,
            color="white", fontweight="bold")

    gr, gc = ambiente.objetivo
    ax.plot(gc + 0.5, gr + 0.5, marker="*", markersize=22, markerfacecolor=COR_OBJETIVO,
            markeredgecolor="white", markeredgewidth=1.1, zorder=4)
    ax.text(gc + 0.5, gr - 0.15, "Prêmio", ha="center", va="bottom", fontsize=7.5,
            color="white", fontweight="bold")

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


def desenhar_legenda() -> None:
    itens = [("Parede", CORES_TERRENO['#']), *[(NOMES_TERRENO[t], CORES_TERRENO[t]) for t in ".:^~"]]
    partes = []
    for texto, cor in itens:
        partes.append(
            f'<span style="display:inline-flex;align-items:center;margin-right:16px;'
            f'font-size:0.8rem;color:#444;">'
            f'<span style="width:12px;height:12px;background:{cor};display:inline-block;'
            f'margin-right:6px;border:1px solid #999;border-radius:2px;"></span>{texto}</span>'
        )
    st.markdown(f'<div style="padding:4px 0 10px 0;">{"".join(partes)}</div>', unsafe_allow_html=True)


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
    ax.set_ylabel("")
    fig.tight_layout()
    return fig


def main() -> None:
    st.set_page_config(page_title="Trabalho 1 — Busca em Grafo", layout="wide")

    if "ambiente" not in st.session_state:
        st.session_state.preset_atual = PRESET_PADRAO
        st.session_state.ambiente = gerar_ambiente_preset(PRESET_PADRAO)
        st.session_state.objetivo_padrao = st.session_state.ambiente.objetivo
        st.session_state.resultado = None
        st.session_state.comparacao = None

    ambiente: Ambiente = st.session_state.ambiente

    st.title("Navegação Autônoma por Busca em Grafo")
    st.caption("Fundamentos de Sistemas Inteligentes — Trabalho 1 (UTFPR) · "
               "Busca em Largura · Busca em Profundidade · Busca Gulosa · A* · "
               "Custo Uniforme")

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
            st.session_state.resultado = None
            st.session_state.comparacao = None
            st.rerun()

        st.divider()
        st.subheader("Algoritmo de busca")
        nome_algoritmo = st.selectbox("Algoritmo", list(ALGORITMOS.keys()), index=3,
                                       label_visibility="collapsed")

        if st.button("Calcular Rota", type="primary", width="stretch"):
            st.session_state.resultado = ALGORITMOS[nome_algoritmo](ambiente)

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
                st.session_state.resultado = None
                st.session_state.comparacao = None
                st.rerun()
        if st.button("Restaurar Objetivo Padrão", width="stretch"):
            ambiente.objetivo = st.session_state.objetivo_padrao
            st.session_state.resultado = None
            st.session_state.comparacao = None
            st.rerun()
        celula_isolada = encontrar_celula_isolada(ambiente)
        if celula_isolada is not None:
            st.caption(f"Dica: linha {celula_isolada[0]}, coluna {celula_isolada[1]} fica "
                       "numa área sem conexão com o início — boa forma de testar a "
                       "detecção de \"sem caminho\".")

        st.divider()
        if st.button("Comparar Algoritmos", width="stretch"):
            st.session_state.comparacao = {nome: executar_com_tempo_medio(algo, ambiente)
                                           for nome, algo in ALGORITMOS.items()}

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
        elif not resultado.encontrou_caminho:
            st.warning(f"[{resultado.nome}] Nenhum caminho encontrado até {ambiente.objetivo}.\n\n"
                       "O destino pode estar isolado por paredes (sem nenhuma porta de acesso) "
                       "ou dentro de um beco sem saída.")
            st.metric("Nós expandidos", resultado.nos_expandidos)
            st.metric("Tempo de execução", f"{resultado.tempo_execucao_s * 1000:.2f} ms")
        else:
            st.success(f"[{resultado.nome}] Caminho encontrado!")
            m1, m2 = st.columns(2)
            m1.metric("Custo total", resultado.custo_total)
            m2.metric("Recompensas", f"{len(resultado.recompensas_coletadas)}/{len(ambiente.recompensas)}")
            m3, m4 = st.columns(2)
            m3.metric(f"Saldo ({VALOR_RECOMPENSA}×$ − custo)", resultado.saldo)
            m4.metric("Nós expandidos", resultado.nos_expandidos)
            m5, m6 = st.columns(2)
            m5.metric("Pico da fronteira", resultado.max_fronteira)
            m6.metric("Tempo", f"{resultado.tempo_execucao_s * 1000:.2f} ms")

    st.divider()
    aba_arvore, aba_comparacao = st.tabs(["Árvore de Busca", "Comparação entre Algoritmos"])

    with aba_arvore:
        if resultado is None:
            st.info("Calcule uma rota primeiro para ver a árvore de busca gerada por ela.")
        else:
            fig_arvore = construir_figura(resultado)
            st.pyplot(fig_arvore, width="stretch")
            plt.close(fig_arvore)
            st.caption("Azul = início · Verde = objetivo · Amarelo = recompensa · "
                       "Laranja = nós/arestas do caminho encontrado.")

    with aba_comparacao:
        comparacao = st.session_state.comparacao
        if comparacao is None:
            st.info("Clique em \"Comparar Algoritmos\" na barra lateral.")
        else:
            st.dataframe(montar_tabela_comparacao(comparacao, ambiente), width="stretch")
            st.caption(f"Saldo = {VALOR_RECOMPENSA} × recompensas − custo do percurso. "
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
