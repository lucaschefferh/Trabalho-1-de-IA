"""
Visualização da árvore de busca gerada por um algoritmo (mostrada depois que
o algoritmo termina, como pedido).

Em vez de depender da biblioteca `networkx` (não instalada por padrão), o
layout da árvore é calculado à mão com um algoritmo simples de posicionamento
por níveis: a profundidade de cada nó vira a coordenada Y, e a coordenada X é
distribuída de forma que folhas fiquem espaçadas uniformemente e nós internos
fiquem centralizados acima de seus filhos (um "Reingold-Tilford" simplificado).
"""

from __future__ import annotations

from collections import defaultdict

from matplotlib.collections import LineCollection
from matplotlib.figure import Figure

from busca import ResultadoBusca

COR_NO_PADRAO = "#9aa5b1"
COR_NO_CAMINHO = "#ff8c42"
COR_NO_RECOMPENSA = "#f2c14e"
COR_NO_INICIO = "#3a86ff"
COR_NO_OBJETIVO = "#2ecc71"
COR_ARESTA_PADRAO = "#c7ccd1"
COR_ARESTA_CAMINHO = "#ff8c42"


def _construir_filhos(pais: dict) -> dict:
    filhos = defaultdict(list)
    for no, pai in pais.items():
        filhos[pai].append(no)
    for lista in filhos.values():
        lista.sort()
    return filhos


def calcular_layout(pais: dict, raiz):
    """Retorna {no: (x, y)} posicionando a raiz no topo (y=0) e descendentes
    em níveis abaixo, com folhas espaçadas uniformemente no eixo X."""
    filhos = _construir_filhos(pais)
    posicoes: dict = {}
    profundidade = {raiz: 0}
    proximo_x = [0]

    pilha = [(raiz, False)]
    while pilha:
        no, processado = pilha.pop()
        if processado:
            filhos_no = filhos.get(no, [])
            if filhos_no:
                xs = [posicoes[f][0] for f in filhos_no]
                x = sum(xs) / len(xs)
            else:
                x = proximo_x[0]
                proximo_x[0] += 1
            posicoes[no] = (x, -profundidade[no])
        else:
            pilha.append((no, True))
            for f in reversed(filhos.get(no, [])):
                profundidade[f] = profundidade[no] + 1
                pilha.append((f, False))

    return posicoes


def _posicao_do_no(no):
    """Nós da árvore são posições (buscas cegas) ou estados (posição, máscara)
    (buscas informadas); devolve a posição em ambos os casos."""
    return no[0] if isinstance(no[0], tuple) else no


def construir_figura(resultado: ResultadoBusca) -> Figure:
    ambiente = resultado.ambiente
    pais = resultado.arvore_pais
    raiz = resultado.raiz

    fig = Figure(figsize=(11, 7), dpi=100)
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor("#1e1f26")
    ax.set_facecolor("#1e1f26")

    if not pais and not resultado.caminho:
        ax.text(0.5, 0.5, "Nenhum nó foi expandido.", ha="center", va="center",
                 color="white", fontsize=14, transform=ax.transAxes)
        ax.axis("off")
        return fig

    posicoes = calcular_layout(pais, raiz)

    caminho = set(resultado.caminho_nos)
    arestas_caminho = set()
    for i in range(len(resultado.caminho_nos) - 1):
        arestas_caminho.add((resultado.caminho_nos[i + 1], resultado.caminho_nos[i]))

    # As árvores das buscas informadas podem ter dezenas de milhares de nós,
    # então arestas e nós são desenhados em lote (LineCollection/um scatter
    # por categoria) em vez de uma chamada de plot por elemento.
    segmentos_normais, segmentos_caminho = [], []
    for no, pai in pais.items():
        if no not in posicoes or pai not in posicoes:
            continue
        segmento = (posicoes[pai], posicoes[no])
        if (no, pai) in arestas_caminho:
            segmentos_caminho.append(segmento)
        else:
            segmentos_normais.append(segmento)
    ax.add_collection(LineCollection(segmentos_normais, colors=COR_ARESTA_PADRAO,
                                     linewidths=0.6, alpha=0.7, zorder=1))
    ax.add_collection(LineCollection(segmentos_caminho, colors=COR_ARESTA_CAMINHO,
                                     linewidths=2.4, zorder=2))

    recompensas = set(ambiente.recompensas)
    categorias = defaultdict(list)
    for no, xy in posicoes.items():
        pos = _posicao_do_no(no)
        if no == raiz:
            categorias[(COR_NO_INICIO, 90, "s")].append(xy)
        elif pos == ambiente.objetivo:
            categorias[(COR_NO_OBJETIVO, 140, "*")].append(xy)
        elif pos in recompensas:
            categorias[(COR_NO_RECOMPENSA, 55, "o")].append(xy)
        elif no in caminho:
            categorias[(COR_NO_CAMINHO, 30, "o")].append(xy)
        else:
            categorias[(COR_NO_PADRAO, 12, "o")].append(xy)
    for (cor, tam, marcador), pontos in categorias.items():
        xs, ys = zip(*pontos)
        ax.scatter(xs, ys, s=tam, c=cor, marker=marcador, zorder=3,
                   edgecolors="#1e1f26", linewidths=0.4)

    # Rótulos só no caminho encontrado (numa árvore de estados a mesma
    # posição aparece várias vezes, uma por combinação de recompensas).
    for no in [raiz, *resultado.caminho_nos]:
        pos = _posicao_do_no(no)
        if no not in posicoes:
            continue
        if no == raiz:
            texto = "Início"
        elif pos == ambiente.objetivo:
            texto = "Objetivo"
        elif pos in recompensas:
            texto = "$"
        else:
            continue
        ax.annotate(texto, posicoes[no], textcoords="offset points", xytext=(0, 8),
                    ha="center", fontsize=8, color="white")

    ax.autoscale_view()
    ax.set_title(
        f"Árvore de busca — {resultado.nome}   "
        f"(expandidos: {resultado.nos_expandidos}, gerados: {resultado.nos_gerados}, "
        f"pico da fronteira: {resultado.max_fronteira}, "
        f"tempo: {resultado.tempo_execucao_s * 1000:.2f} ms)",
        color="white", fontsize=11,
    )
    ax.axis("off")
    fig.tight_layout()
    return fig
