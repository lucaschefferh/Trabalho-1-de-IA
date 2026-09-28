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

import tkinter as tk
from collections import defaultdict

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
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

    return posicoes, filhos


def construir_figura(resultado: ResultadoBusca) -> Figure:
    ambiente = resultado.ambiente
    pais = resultado.arvore_pais
    raiz = ambiente.inicio

    fig = Figure(figsize=(11, 7), dpi=100)
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor("#1e1f26")
    ax.set_facecolor("#1e1f26")

    if not pais and raiz != ambiente.objetivo:
        ax.text(0.5, 0.5, "Nenhum nó foi expandido.", ha="center", va="center",
                 color="white", fontsize=14, transform=ax.transAxes)
        ax.axis("off")
        return fig

    posicoes, _ = calcular_layout(pais, raiz)

    caminho = set(resultado.caminho or [])
    arestas_caminho = set()
    if resultado.caminho:
        for i in range(len(resultado.caminho) - 1):
            arestas_caminho.add((resultado.caminho[i + 1], resultado.caminho[i]))

    # arestas normais primeiro, depois as do caminho (para ficarem por cima)
    for no, pai in pais.items():
        if no not in posicoes or pai not in posicoes:
            continue
        x0, y0 = posicoes[pai]
        x1, y1 = posicoes[no]
        destaque = (no, pai) in arestas_caminho
        if not destaque:
            ax.plot([x0, x1], [y0, y1], color=COR_ARESTA_PADRAO, linewidth=0.6,
                     zorder=1, alpha=0.7)
    for no, pai in pais.items():
        if no not in posicoes or pai not in posicoes:
            continue
        if (no, pai) in arestas_caminho:
            x0, y0 = posicoes[pai]
            x1, y1 = posicoes[no]
            ax.plot([x0, x1], [y0, y1], color=COR_ARESTA_CAMINHO, linewidth=2.4,
                     zorder=2)

    recompensas = set(ambiente.recompensas)
    for no, (x, y) in posicoes.items():
        if no == raiz:
            cor, tam, marcador = COR_NO_INICIO, 90, "s"
        elif no == ambiente.objetivo:
            cor, tam, marcador = COR_NO_OBJETIVO, 140, "*"
        elif no in recompensas:
            cor, tam, marcador = COR_NO_RECOMPENSA, 55, "o"
        elif no in caminho:
            cor, tam, marcador = COR_NO_CAMINHO, 30, "o"
        else:
            cor, tam, marcador = COR_NO_PADRAO, 12, "o"
        ax.scatter([x], [y], s=tam, c=cor, marker=marcador, zorder=3,
                   edgecolors="#1e1f26", linewidths=0.4)

    for no in (raiz, ambiente.objetivo, *recompensas):
        if no in posicoes:
            x, y = posicoes[no]
            texto = "Início" if no == raiz else ("Objetivo" if no == ambiente.objetivo else "$")
            ax.annotate(texto, (x, y), textcoords="offset points", xytext=(0, 8),
                        ha="center", fontsize=8, color="white")

    ax.set_title(
        f"Árvore de busca — {resultado.nome}   "
        f"(nós expandidos: {resultado.nos_expandidos}, "
        f"tempo: {resultado.tempo_execucao_s * 1000:.2f} ms)",
        color="white", fontsize=12,
    )
    ax.axis("off")
    fig.tight_layout()
    return fig


def mostrar_janela_arvore(parent: tk.Widget, resultado: ResultadoBusca) -> None:
    janela = tk.Toplevel(parent)
    janela.title(f"Árvore de Busca — {resultado.nome}")
    janela.geometry("1000x720")
    janela.configure(bg="#1e1f26")

    fig = construir_figura(resultado)
    canvas = FigureCanvasTkAgg(fig, master=janela)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    barra = NavigationToolbar2Tk(canvas, janela)
    barra.configure(background="#1e1f26")
    barra.update()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    legenda = tk.Label(
        janela,
        text="Azul = início   Verde = objetivo   Amarelo = recompensa   "
             "Laranja = nós/arestas do caminho encontrado   "
             "Use a lupa da barra de ferramentas para dar zoom.",
        bg="#1e1f26", fg="white", font=("Segoe UI", 9), pady=6,
    )
    legenda.pack(fill=tk.X)
