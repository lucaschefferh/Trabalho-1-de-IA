"""
Implementação dos algoritmos de busca pedidos no trabalho — Busca em Largura
(BFS), Busca em Profundidade (DFS), Busca Gulosa e A* — e, como referência
extra, a Busca de Custo Uniforme (Dijkstra), que é o A* com h(n) = 0.

Todos devolvem um `ResultadoBusca` com o caminho, o custo, as recompensas
coletadas e as métricas usadas no comparativo: nós expandidos, nós gerados,
pico da fronteira (memória) e tempo de execução.

Buscas cegas (BFS e DFS)
------------------------
Operam sobre o grafo do mapa: o estado é apenas a posição do agente. Não
"enxergam" recompensas nem custos de terreno; o agente coleta as recompensas
que estiverem nos vértices do caminho encontrado até o prêmio.

Buscas informadas (Gulosa, A* e Custo Uniforme)
-----------------------------------------------
Para que o algoritmo consiga decidir se *compensa desviar* da rota para pegar
uma recompensa, isso precisa fazer parte do problema, e não só da heurística.
Formulação:

  * Estado: s = (p, M), onde p é a posição e M é a máscara de bits das
    recompensas (alcançáveis) já coletadas. Entrar numa célula com recompensa
    liga o bit correspondente.
  * Ação: mover para um vizinho ortogonal; custo = custo do terreno de destino.
  * Estado final: qualquer s com p = prêmio. Ao terminar, paga-se um custo
    terminal de V por recompensa não coletada (V = VALOR_RECOMPENSA).

  Custo total J = Σ custos de terreno + V · (recompensas deixadas para trás)

Minimizar J equivale a maximizar o saldo = V · coletadas − custo do percurso.
Assim, desviar até uma recompensa compensa exatamente quando o custo extra do
desvio é menor que V. Todos os custos são não negativos, então as garantias
clássicas do A* continuam valendo.

Recompensas fora da componente conexa do início (ex.: sala sem portas) são
descartadas antes da busca: não há como coletá-las, e mantê-las só
multiplicaria o espaço de estados sem mudar a decisão.
"""

from __future__ import annotations

import heapq
import time
from dataclasses import dataclass, field
from typing import Callable, Hashable, Iterable

from mapa import Ambiente

Posicao = tuple[int, int]
Estado = tuple[Posicao, int]  # (posição, máscara de recompensas coletadas)

VALOR_RECOMPENSA = 15  # V: quanto vale cada recompensa, na mesma unidade do custo

# Comparativo de tempo: cada algoritmo é repetido até REPETICOES_TEMPO vezes
# (ou até estourar ORCAMENTO_TEMPO_S) e o tempo reportado é a média.
REPETICOES_TEMPO = 30
ORCAMENTO_TEMPO_S = 1.0


# --- Heurísticas -------------------------------------------------------------
#
# d(a, b) = distância de Manhattan. Como o agente anda em 4 direções e o
# terreno mais barato custa 1, d(a, b) nunca supera o custo real de a até b.
#
# Para cada recompensa r ainda não coletada, a partir da posição p:
#
#   desvio(p, r) = d(p, r) + d(r, G) − d(p, G)   (≥ 0 pela desig. triangular)
#   c(p, r)      = min(V, desvio(p, r))
#
# c(p, r) é o menor preço que r ainda pode cobrar do agente: ou ele desvia
# (e paga ao menos `desvio` a mais de caminho), ou a deixa para trás (e paga V).
# É aqui que a heurística "avalia se compensa desviar": recompensas próximas
# da rota têm c pequeno; recompensas longe ficam limitadas a V, ou seja, a
# heurística já assume que elas serão abandonadas.
#
# A*:     h(p, M) = d(p, G) + max_r c(p, r)
#   Admissível: para qualquer r, a solução ótima a partir de p ou passa por r
#   (custo ≥ d(p,r) + d(r,G) = d(p,G) + desvio) ou não passa (custo ≥ d(p,G) + V).
#   Logo o custo real é ≥ d(p,G) + c(p,r) para todo r, e portanto ≥ o máximo.
#   Não é necessariamente consistente, por isso o A* reabre nós (ver abaixo).
#
# Gulosa: h(p, M) = d(p, G) + Σ_r c(p, r)
#   Soma a contribuição de todas as recompensas: é mais informativa para
#   guiar a busca na direção de grupos de recompensas, mas não é admissível
#   (desvios para recompensas vizinhas compartilham passos). Para a Gulosa isso
#   não importa: ela já não garante o ótimo, só busca chegar rápido.


def distancia_manhattan(a: Posicao, b: Posicao) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _custos_recompensas(pos: Posicao, objetivo: Posicao,
                         restantes: Iterable[Posicao]) -> tuple[int, list[int]]:
    d_obj = distancia_manhattan(pos, objetivo)
    custos = []
    for r in restantes:
        desvio = distancia_manhattan(pos, r) + distancia_manhattan(r, objetivo) - d_obj
        custos.append(min(VALOR_RECOMPENSA, desvio))
    return d_obj, custos


def heuristica_a_estrela(pos: Posicao, objetivo: Posicao,
                          restantes: Iterable[Posicao]) -> int:
    d_obj, custos = _custos_recompensas(pos, objetivo, restantes)
    return d_obj + max(custos, default=0)


def heuristica_gulosa(pos: Posicao, objetivo: Posicao,
                       restantes: Iterable[Posicao]) -> int:
    d_obj, custos = _custos_recompensas(pos, objetivo, restantes)
    return d_obj + sum(custos)


def heuristica_nula(_pos: Posicao, _objetivo: Posicao, _restantes: Iterable[Posicao]) -> int:
    return 0


# --- Resultado ---------------------------------------------------------------

@dataclass
class ResultadoBusca:
    nome: str
    ambiente: Ambiente
    caminho: list[Posicao] | None
    custo_total: float
    recompensas_coletadas: list[Posicao]
    nos_expandidos: int
    nos_gerados: int
    max_fronteira: int
    tempo_execucao_s: float
    # Árvore de busca: nós são posições (buscas cegas) ou estados (p, M)
    # (buscas informadas). `caminho_nos` é o caminho expresso nesses nós.
    arvore_pais: dict[Hashable, Hashable] = field(default_factory=dict)
    raiz: Hashable = None
    caminho_nos: list[Hashable] = field(default_factory=list)
    repeticoes_tempo: int = 1

    @property
    def encontrou_caminho(self) -> bool:
        return self.caminho is not None

    @property
    def saldo(self) -> float:
        """V · recompensas coletadas − custo do percurso (quanto maior, melhor)."""
        return VALOR_RECOMPENSA * len(self.recompensas_coletadas) - self.custo_total


def _reconstruir(pais: dict, raiz, final) -> list:
    caminho = [final]
    while caminho[-1] != raiz:
        caminho.append(pais[caminho[-1]])
    caminho.reverse()
    return caminho


def _custo_do_caminho(ambiente: Ambiente, caminho: list[Posicao]) -> int:
    return sum(ambiente.custo_aresta(caminho[i], caminho[i + 1])
               for i in range(len(caminho) - 1))


def _empacotar_resultado(nome: str, ambiente: Ambiente, pais: dict, raiz, final,
                          posicao_do_no: Callable[[Hashable], Posicao],
                          nos_expandidos: int, nos_gerados: int, max_fronteira: int,
                          tempo_inicio: float) -> ResultadoBusca:
    tempo_execucao = time.perf_counter() - tempo_inicio
    metricas = dict(nome=nome, ambiente=ambiente, nos_expandidos=nos_expandidos,
                    nos_gerados=nos_gerados, max_fronteira=max_fronteira,
                    tempo_execucao_s=tempo_execucao, arvore_pais=pais, raiz=raiz)
    if final is None:
        return ResultadoBusca(caminho=None, custo_total=0, recompensas_coletadas=[],
                              **metricas)
    caminho_nos = _reconstruir(pais, raiz, final)
    caminho = [posicao_do_no(no) for no in caminho_nos]
    presentes = set(caminho)
    recompensas = [r for r in ambiente.recompensas if r in presentes]
    return ResultadoBusca(caminho=caminho, custo_total=_custo_do_caminho(ambiente, caminho),
                          recompensas_coletadas=recompensas, caminho_nos=caminho_nos,
                          **metricas)


def _identidade(pos: Posicao) -> Posicao:
    return pos


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
    nos_gerados = 1
    max_fronteira = 1
    final = None

    idx = 0
    while idx < len(fronteira):
        max_fronteira = max(max_fronteira, len(fronteira) - idx)
        atual = fronteira[idx]
        idx += 1
        nos_expandidos += 1
        if atual == objetivo:
            final = atual
            break
        for viz in ambiente.vizinhos(atual):
            if viz not in visitados:
                visitados.add(viz)
                pais[viz] = atual
                fronteira.append(viz)
                nos_gerados += 1

    return _empacotar_resultado("Busca em Largura", ambiente, pais, inicio, final,
                                _identidade, nos_expandidos, nos_gerados, max_fronteira, t0)


def busca_em_profundidade(ambiente: Ambiente) -> ResultadoBusca:
    """DFS: mergulha por um ramo até o fim antes de tentar outro. Acha *um*
    caminho, sem garantia de ser o mais curto nem o de menor custo."""
    t0 = time.perf_counter()
    inicio, objetivo = ambiente.inicio, ambiente.objetivo
    pilha: list[Posicao] = [inicio]
    visitados = {inicio}
    pais: dict[Posicao, Posicao] = {}
    nos_expandidos = 0
    nos_gerados = 1
    max_fronteira = 1
    final = None

    while pilha:
        max_fronteira = max(max_fronteira, len(pilha))
        atual = pilha.pop()
        nos_expandidos += 1
        if atual == objetivo:
            final = atual
            break
        for viz in ambiente.vizinhos(atual):
            if viz not in visitados:
                visitados.add(viz)
                pais[viz] = atual
                pilha.append(viz)
                nos_gerados += 1

    return _empacotar_resultado("Busca em Profundidade", ambiente, pais, inicio, final,
                                _identidade, nos_expandidos, nos_gerados, max_fronteira, t0)


# --- Buscas informadas -------------------------------------------------------

def _busca_espaco_estados(ambiente: Ambiente, nome: str,
                           heuristica: Callable[[Posicao, Posicao, Iterable[Posicao]], float],
                           usa_custo_acumulado: bool) -> ResultadoBusca:
    """Busca de melhor escolha sobre os estados (posição, máscara).

    Prioridade de um estado s com custo acumulado g:
      * s não final: g + h(s) no A*/Custo Uniforme, ou só h(s) na Gulosa;
      * s final (no prêmio): o restante do custo é conhecido exatamente — o
        custo terminal V · (recompensas não coletadas) — e é usado no lugar de h.

    A* e Custo Uniforme reabrem um estado sempre que acham um caminho mais
    barato até ele (entradas obsoletas no heap são descartadas ao sair). Isso é
    necessário porque a heurística do A* é admissível mas não consistente.
    Com isso, o primeiro estado final retirado do heap é ótimo.

    A Gulosa usa busca em grafo clássica: cada estado é gerado uma única vez
    e fechado ao ser expandido; o custo acumulado não influencia a ordem. Ela
    para assim que *gera* um estado no prêmio (teste de objetivo na geração):
    se esperasse o estado final sair do heap com prioridade V · faltando, ela
    continuaria procurando combinações melhores de recompensas e acabaria
    varrendo quase todo o espaço de estados — virando uma busca exaustiva, o
    oposto do que se espera de uma estratégia gulosa.
    """
    t0 = time.perf_counter()
    inicio, objetivo = ambiente.inicio, ambiente.objetivo

    alcancaveis = ambiente.alcancaveis(inicio)
    recompensas = [r for r in ambiente.recompensas if r in alcancaveis]
    bit_de = {r: 1 << i for i, r in enumerate(recompensas)}

    def entrar(pos: Posicao, mascara: int) -> Estado:
        return pos, mascara | bit_de.get(pos, 0)

    def prioridade(estado: Estado, g: float) -> float:
        pos, mascara = estado
        if pos == objetivo:
            faltando = len(recompensas) - bin(mascara).count("1")
            return g + VALOR_RECOMPENSA * faltando
        restantes = [r for r in recompensas if not mascara & bit_de[r]]
        h = heuristica(pos, objetivo, restantes)
        return g + h if usa_custo_acumulado else h

    estado_inicial = entrar(inicio, 0)
    g_score: dict[Estado, float] = {estado_inicial: 0}
    pais: dict[Estado, Estado] = {}
    fechados: set[Estado] = set()
    contador = 0  # desempate FIFO estável no heap
    heap = [(prioridade(estado_inicial, 0), 0, contador, estado_inicial)]
    nos_expandidos = 0
    nos_gerados = 1
    max_fronteira = 1
    final = None

    while heap:
        max_fronteira = max(max_fronteira, len(heap))
        _, g_no_push, _, atual = heapq.heappop(heap)
        if usa_custo_acumulado:
            if g_no_push > g_score[atual]:
                continue  # entrada obsoleta: já existe caminho melhor até "atual"
        else:
            if atual in fechados:
                continue
            fechados.add(atual)
        nos_expandidos += 1

        pos, mascara = atual
        if pos == objetivo:
            final = atual
            break

        g_atual = g_score[atual]
        for viz in ambiente.vizinhos(pos):
            novo = entrar(viz, mascara)
            novo_g = g_atual + ambiente.custo_aresta(pos, viz)
            if usa_custo_acumulado:
                if novo_g >= g_score.get(novo, float("inf")):
                    continue
            elif novo in g_score:
                continue
            g_score[novo] = novo_g
            pais[novo] = atual
            contador += 1
            nos_gerados += 1
            if not usa_custo_acumulado and viz == objetivo:
                final = novo  # Gulosa: teste de objetivo na geração
                break
            heapq.heappush(heap, (prioridade(novo, novo_g), novo_g, contador, novo))
        if final is not None:
            break

    return _empacotar_resultado(nome, ambiente, pais, estado_inicial, final,
                                lambda estado: estado[0], nos_expandidos, nos_gerados,
                                max_fronteira, t0)


def busca_gulosa(ambiente: Ambiente) -> ResultadoBusca:
    """Gulosa: expande sempre o estado com menor h (distância ao prêmio +
    preço estimado de cada recompensa restante), ignorando o custo já gasto.
    Tende a coletar muitas recompensas, mas sem garantia de saldo ótimo."""
    return _busca_espaco_estados(ambiente, "Busca Gulosa", heuristica_gulosa,
                                 usa_custo_acumulado=False)


def busca_a_estrela(ambiente: Ambiente) -> ResultadoBusca:
    """A*: ordena por f = g + h com h admissível; devolve a rota de menor
    custo total J, desviando para recompensas só quando o desvio compensa."""
    return _busca_espaco_estados(ambiente, "A*", heuristica_a_estrela,
                                 usa_custo_acumulado=True)


def busca_custo_uniforme(ambiente: Ambiente) -> ResultadoBusca:
    """Custo Uniforme (Dijkstra): A* com h = 0. Também é ótimo, e serve de
    referência para medir quantos nós a heurística do A* economiza."""
    return _busca_espaco_estados(ambiente, "Custo Uniforme", heuristica_nula,
                                 usa_custo_acumulado=True)


ALGORITMOS: dict[str, Callable[[Ambiente], ResultadoBusca]] = {
    "Busca em Largura": busca_em_largura,
    "Busca em Profundidade": busca_em_profundidade,
    "Busca Gulosa": busca_gulosa,
    "A*": busca_a_estrela,
    "Custo Uniforme": busca_custo_uniforme,
}


def executar_com_tempo_medio(algoritmo: Callable[[Ambiente], ResultadoBusca],
                              ambiente: Ambiente) -> ResultadoBusca:
    """Executa o algoritmo várias vezes e reporta o tempo médio — uma única
    medição abaixo de 1 ms é dominada por ruído do sistema operacional."""
    resultado = algoritmo(ambiente)
    tempos = [resultado.tempo_execucao_s]
    while len(tempos) < REPETICOES_TEMPO and sum(tempos) < ORCAMENTO_TEMPO_S:
        tempos.append(algoritmo(ambiente).tempo_execucao_s)
    resultado.tempo_execucao_s = sum(tempos) / len(tempos)
    resultado.repeticoes_tempo = len(tempos)
    return resultado
