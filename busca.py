"""
Implementação dos quatro algoritmos de busca pedidos no trabalho:
Busca em Largura (BFS), Busca em Profundidade (DFS), Busca Gulosa e A*.

Todos operam sobre o grafo implícito definido por `mapa.Ambiente` (cada
célula andável é um vértice, ligado aos vizinhos ortogonais) e devolvem um
`ResultadoBusca` com o caminho encontrado, o custo total, as recompensas
coletadas no percurso, e métricas de desempenho (nós expandidos e tempo de
execução) para a comparação pedida no enunciado.

Todos são implementados como "busca em grafo" (mantêm um conjunto de nós já
fechados) para não entrar em loop infinito nos ciclos do mapa — sem isso a
Busca em Profundidade, em particular, nunca terminaria neste ambiente.
"""

from __future__ import annotations

import heapq
import time
from dataclasses import dataclass, field
from typing import Callable

from mapa import Ambiente

Posicao = tuple[int, int]

# --- Heurística ------------------------------------------------------------
#
# Para Gulosa e A*, a heurística não é só a distância até o objetivo: o
# enunciado pede que ela avalie se compensa desviar da rota para pegar uma
# recompensa próxima. Modelamos isso assim:
#
#   h(n) = distancia_ate_objetivo(n)
#          - soma, para cada recompensa ainda não coletada, do ganho líquido
#            estimado de desviar até ela (valor da recompensa menos o custo
#            extra estimado do desvio), quando esse ganho é positivo.
#
# Ou seja: um nó perto de uma recompensa "valiosa" (cujo desvio compensa)
# recebe heurística menor (mais atraente), incentivando o algoritmo a passar
# por perto dela sem abandonar de vez o rumo do objetivo.
#
# Como só SUBTRAÍMOS um bônus não-negativo de uma base admissível (distância
# Manhattan, que nunca superestima o custo real já que o terreno mais barato
# custa 1), h(n) continua *admissível* (h(n) <= custo real até o objetivo).
# Mas ela deixa de ser *consistente* (h(n) <= custo(n, n') + h(n') para toda
# aresta) — o bônus pode saltar de forma brusca entre dois vizinhos quando um
# deles entra no raio de influência de uma recompensa e o outro não. Por isso
# `_busca_informada` NÃO usa um conjunto de nós fechados permanente: ela
# reabre um nó sempre que encontra um caminho mais barato até ele. Isso é
# obrigatório para o A* continuar garantindo o menor custo quando a
# heurística é apenas admissível (sem reabertura, um nó fechado cedo demais
# com heurística inconsistente pode nunca mais ser corrigido).

VALOR_RECOMPENSA = 15       # valor "assumido" de cada recompensa
CUSTO_MEDIO_TERRENO = 3     # custo médio estimado por passo de desvio
RAIO_INFLUENCIA_RECOMPENSA = 12  # além dessa distância, a recompensa não pesa


def distancia_manhattan(a: Posicao, b: Posicao) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def heuristica(no: Posicao, objetivo: Posicao,
               recompensas_restantes: frozenset[Posicao]) -> float:
    h_base = distancia_manhattan(no, objetivo)

    bonus = 0.0
    for r in recompensas_restantes:
        dist_no_ate_recompensa = distancia_manhattan(no, r)
        if dist_no_ate_recompensa > RAIO_INFLUENCIA_RECOMPENSA:
            continue
        dist_recompensa_ate_objetivo = distancia_manhattan(r, objetivo)
        custo_desvio = (dist_no_ate_recompensa + dist_recompensa_ate_objetivo) - h_base
        ganho_liquido = VALOR_RECOMPENSA - custo_desvio * CUSTO_MEDIO_TERRENO
        if ganho_liquido > 0:
            bonus += ganho_liquido

    return max(0.0, h_base - bonus)


@dataclass
class ResultadoBusca:
    nome: str
    ambiente: Ambiente
    caminho: list[Posicao] | None
    custo_total: float
    recompensas_coletadas: list[Posicao]
    nos_expandidos: int
    tempo_execucao_s: float
    arvore_pais: dict[Posicao, Posicao] = field(default_factory=dict)

    @property
    def encontrou_caminho(self) -> bool:
        return self.caminho is not None


def _reconstruir_caminho(pais: dict[Posicao, Posicao], inicio: Posicao,
                          objetivo: Posicao) -> list[Posicao]:
    caminho = [objetivo]
    atual = objetivo
    while atual != inicio:
        atual = pais[atual]
        caminho.append(atual)
    caminho.reverse()
    return caminho


def _custo_do_caminho(ambiente: Ambiente, caminho: list[Posicao]) -> int:
    return sum(ambiente.custo_aresta(caminho[i], caminho[i + 1])
               for i in range(len(caminho) - 1))


def _recompensas_no_caminho(ambiente: Ambiente, caminho: list[Posicao]) -> list[Posicao]:
    presentes = set(caminho)
    return [r for r in ambiente.recompensas if r in presentes]


def _empacotar_resultado(nome: str, ambiente: Ambiente, pais: dict[Posicao, Posicao],
                          nos_expandidos: int, tempo_inicio: float) -> ResultadoBusca:
    tempo_execucao = time.perf_counter() - tempo_inicio
    if ambiente.objetivo not in pais and ambiente.objetivo != ambiente.inicio:
        return ResultadoBusca(nome=nome, ambiente=ambiente, caminho=None, custo_total=0,
                               recompensas_coletadas=[], nos_expandidos=nos_expandidos,
                               tempo_execucao_s=tempo_execucao, arvore_pais=pais)
    caminho = _reconstruir_caminho(pais, ambiente.inicio, ambiente.objetivo)
    custo = _custo_do_caminho(ambiente, caminho)
    recompensas = _recompensas_no_caminho(ambiente, caminho)
    return ResultadoBusca(nome=nome, ambiente=ambiente, caminho=caminho, custo_total=custo,
                           recompensas_coletadas=recompensas, nos_expandidos=nos_expandidos,
                           tempo_execucao_s=tempo_execucao, arvore_pais=pais)


# --- Buscas cegas ------------------------------------------------------------

def busca_em_largura(ambiente: Ambiente) -> ResultadoBusca:
    """BFS: explora por camadas (nº de arestas), ignorando o custo do
    terreno. Encontra o caminho com menos passos, não o de menor custo."""
    t0 = time.perf_counter()
    inicio, objetivo = ambiente.inicio, ambiente.objetivo
    fronteira: list[Posicao] = [inicio]
    visitados = {inicio}
    pais: dict[Posicao, Posicao] = {}
    nos_expandidos = 0

    if inicio == objetivo:
        return _empacotar_resultado("Busca em Largura", ambiente, pais, 0, t0)

    idx = 0
    while idx < len(fronteira):
        atual = fronteira[idx]
        idx += 1
        nos_expandidos += 1
        if atual == objetivo:
            break
        for viz in ambiente.vizinhos(atual):
            if viz not in visitados:
                visitados.add(viz)
                pais[viz] = atual
                fronteira.append(viz)

    return _empacotar_resultado("Busca em Largura", ambiente, pais, nos_expandidos, t0)


def busca_em_profundidade(ambiente: Ambiente) -> ResultadoBusca:
    """DFS: mergulha por um ramo até o fim antes de tentar outro. Acha *um*
    caminho, sem garantia de ser o mais curto nem o de menor custo."""
    t0 = time.perf_counter()
    inicio, objetivo = ambiente.inicio, ambiente.objetivo
    pilha: list[Posicao] = [inicio]
    visitados = {inicio}
    pais: dict[Posicao, Posicao] = {}
    nos_expandidos = 0

    if inicio == objetivo:
        return _empacotar_resultado("Busca em Profundidade", ambiente, pais, 0, t0)

    while pilha:
        atual = pilha.pop()
        nos_expandidos += 1
        if atual == objetivo:
            break
        for viz in ambiente.vizinhos(atual):
            if viz not in visitados:
                visitados.add(viz)
                pais[viz] = atual
                pilha.append(viz)

    return _empacotar_resultado("Busca em Profundidade", ambiente, pais, nos_expandidos, t0)


# --- Buscas informadas -------------------------------------------------------

def _busca_informada(ambiente: Ambiente, nome: str,
                      usa_custo_acumulado: bool) -> ResultadoBusca:
    """Base comum para Gulosa (usa_custo_acumulado=False, ordena só por h) e
    A* (usa_custo_acumulado=True, ordena por f = g + h).

    Não usa um conjunto de "nós fechados" permanente: cada entrada na heap
    carrega o g com que foi criada, e uma entrada é descartada como obsoleta
    se, quando sai da heap, já existe um g melhor registrado para aquele nó
    (`g_score`). Isso permite reabrir um nó quando um caminho mais barato até
    ele é encontrado depois — necessário para o A* ficar correto com uma
    heurística apenas admissível (não necessariamente consistente), como é o
    caso aqui por causa do bônus de recompensa."""
    t0 = time.perf_counter()
    inicio, objetivo = ambiente.inicio, ambiente.objetivo
    recompensas_restantes = frozenset(ambiente.recompensas)

    contador = 0  # desempate estável no heap
    g_score: dict[Posicao, float] = {inicio: 0}
    pais: dict[Posicao, Posicao] = {}

    h_inicio = heuristica(inicio, objetivo, recompensas_restantes)
    prioridade_inicial = (0 + h_inicio) if usa_custo_acumulado else h_inicio
    heap = [(prioridade_inicial, 0, contador, inicio)]  # (prioridade, g_no_push, desempate, nó)
    nos_expandidos = 0

    while heap:
        _, g_no_push, _, atual = heapq.heappop(heap)
        if g_no_push > g_score.get(atual, float("inf")):
            continue  # entrada obsoleta: já existe um caminho melhor até "atual"
        nos_expandidos += 1

        if atual == objetivo:
            break

        g_atual = g_score[atual]
        for viz in ambiente.vizinhos(atual):
            novo_g = g_atual + ambiente.custo_aresta(atual, viz)
            if novo_g < g_score.get(viz, float("inf")):
                g_score[viz] = novo_g
                pais[viz] = atual
                h = heuristica(viz, objetivo, recompensas_restantes)
                prioridade = (novo_g + h) if usa_custo_acumulado else h
                contador += 1
                heapq.heappush(heap, (prioridade, novo_g, contador, viz))

    return _empacotar_resultado(nome, ambiente, pais, nos_expandidos, t0)


def busca_gulosa(ambiente: Ambiente) -> ResultadoBusca:
    """Gulosa: escolhe sempre o vizinho que parece mais promissor segundo a
    heurística (distância + atratividade das recompensas), ignorando quanto
    já custou para chegar até ali."""
    return _busca_informada(ambiente, "Busca Gulosa", usa_custo_acumulado=False)


def busca_a_estrela(ambiente: Ambiente) -> ResultadoBusca:
    """A*: combina o custo já gasto (g) com a heurística (h), equilibrando
    caminho barato percorrido com promessa futura — inclusive a de
    recompensas próximas que compensa coletar."""
    return _busca_informada(ambiente, "A*", usa_custo_acumulado=True)


ALGORITMOS: dict[str, Callable[[Ambiente], ResultadoBusca]] = {
    "Busca em Largura": busca_em_largura,
    "Busca em Profundidade": busca_em_profundidade,
    "Busca Gulosa": busca_gulosa,
    "A*": busca_a_estrela,
}
