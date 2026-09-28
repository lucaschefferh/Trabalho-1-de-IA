"""
Ambiente do agente: um mapa em grade onde cada célula andável é um vértice
de um grafo, conectado aos seus vizinhos ortogonais (cima/baixo/esquerda/
direita). Paredes bloqueiam totalmente a passagem.

O mapa é gerado proceduralmente (algoritmo de "recursive backtracker" para
labirintos, com adição de laços/atalhos para deixar de ser um labirinto
"perfeito" e virar um grafo com múltiplos caminhos possíveis, como pede o
enunciado). A geração usa uma seed fixa, então o resultado é sempre o mesmo
mapa — ele funciona como um cenário fixo, só que descrito por código em vez
de uma string gigante.

Tipos de terreno e custo de entrar na célula:
    '.'  sólido e plano  -> 1
    ':'  arenoso         -> 4
    '^'  rochoso         -> 10
    '~'  pântano         -> 20
    '#'  parede (intransponível)
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field

CUSTOS_TERRENO = {
    '.': 1,   # sólido e plano
    ':': 4,   # arenoso
    '^': 10,  # rochoso
    '~': 20,  # pântano
}

SEED = 42
ROWS = 15
COLS_LABIRINTO = 21
LARGURA_SALA_ISOLADA = 4
NUM_RECOMPENSAS = 6

# Formatos de labirinto prontos para escolher na interface — cada um varia
# tamanho, seed e fração de laços/atalhos, mudando bastante a "cara" do
# ambiente e, por consequência, o comportamento dos algoritmos de busca.
PRESETS_LABIRINTO: dict[str, dict] = {
    "Padrão (21×15)": dict(seed=42, rows=15, cols_labirinto=21, fracao_lacos=0.15,
                            num_recompensas=6),
    "Compacto (15×11)": dict(seed=5, rows=11, cols_labirinto=15, fracao_lacos=0.15,
                              num_recompensas=5),
    "Grande (31×19)": dict(seed=99, rows=19, cols_labirinto=31, fracao_lacos=0.15,
                            num_recompensas=9),
    "Denso — poucos atalhos (21×15)": dict(seed=7, rows=15, cols_labirinto=21,
                                            fracao_lacos=0.03, num_recompensas=6),
    "Aberto — muitos atalhos (21×15)": dict(seed=7, rows=15, cols_labirinto=21,
                                             fracao_lacos=0.35, num_recompensas=6),
}
PRESET_PADRAO = "Padrão (21×15)"


def _gerar_labirinto(rows: int, cols: int, rng: random.Random) -> list[list[str]]:
    grid = [['#'] * cols for _ in range(rows)]
    visitado = set()
    inicio = (1, 1)
    pilha = [inicio]
    visitado.add(inicio)
    grid[1][1] = '.'
    while pilha:
        r, c = pilha[-1]
        vizinhos = []
        for dr, dc in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            nr, nc = r + dr, c + dc
            if 1 <= nr < rows - 1 and 1 <= nc < cols - 1 and (nr, nc) not in visitado:
                vizinhos.append((nr, nc, dr, dc))
        if vizinhos:
            nr, nc, dr, dc = rng.choice(vizinhos)
            grid[r + dr // 2][c + dc // 2] = '.'
            grid[nr][nc] = '.'
            visitado.add((nr, nc))
            pilha.append((nr, nc))
        else:
            pilha.pop()
    return grid


def _adicionar_lacos(grid: list[list[str]], rng: random.Random, rows: int, cols: int,
                      fracao: float = 0.15) -> None:
    """Derruba algumas paredes internas para criar caminhos alternativos,
    transformando o labirinto 'perfeito' (uma única rota entre dois pontos)
    em um grafo com laços — essencial para a busca ter escolhas reais."""
    candidatos = []
    for r in range(1, rows - 1):
        for c in range(1, cols - 1):
            if grid[r][c] != '#':
                continue
            if r % 2 == 1 and grid[r][c - 1] != '#' and grid[r][c + 1] != '#':
                candidatos.append((r, c))
            elif c % 2 == 1 and grid[r - 1][c] != '#' and grid[r + 1][c] != '#':
                candidatos.append((r, c))
    rng.shuffle(candidatos)
    for r, c in candidatos[: int(len(candidatos) * fracao)]:
        grid[r][c] = '.'


def _bfs_distancias(grid: list[list[str]], origem: tuple[int, int],
                     rows: int, cols: int) -> dict[tuple[int, int], int]:
    dist = {origem: 0}
    fila = deque([origem])
    while fila:
        r, c = fila.popleft()
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] != '#' \
                    and (nr, nc) not in dist:
                dist[(nr, nc)] = dist[(r, c)] + 1
                fila.append((nr, nc))
    return dist


@dataclass
class Ambiente:
    grid: list[str]
    inicio: tuple[int, int]
    objetivo: tuple[int, int]
    recompensas: list[tuple[int, int]]
    linhas: int = field(init=False)
    colunas: int = field(init=False)

    def __post_init__(self) -> None:
        self.linhas = len(self.grid)
        self.colunas = len(self.grid[0])

    def eh_parede(self, pos: tuple[int, int]) -> bool:
        r, c = pos
        if not (0 <= r < self.linhas and 0 <= c < self.colunas):
            return True
        return self.grid[r][c] == '#'

    def custo_terreno(self, pos: tuple[int, int]) -> int:
        r, c = pos
        return CUSTOS_TERRENO[self.grid[r][c]]

    def vizinhos(self, pos: tuple[int, int]):
        r, c = pos
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            viz = (r + dr, c + dc)
            if not self.eh_parede(viz):
                yield viz

    def custo_aresta(self, _origem: tuple[int, int], destino: tuple[int, int]) -> int:
        """Custo de se mover para `destino`: o custo é definido pelo terreno
        que o agente está pisando ao chegar na célula."""
        return self.custo_terreno(destino)


def gerar_ambiente(seed: int = SEED, rows: int = ROWS, cols_labirinto: int = COLS_LABIRINTO,
                    largura_sala_isolada: int = LARGURA_SALA_ISOLADA,
                    num_recompensas: int = NUM_RECOMPENSAS,
                    fracao_lacos: float = 0.15) -> Ambiente:
    """Gera um ambiente determinístico (mesma seed => mesmo mapa). Os
    parâmetros controlam o "formato" do labirinto: tamanho, quantidade de
    atalhos/laços e número de recompensas — usados pelos presets em
    `PRESETS_LABIRINTO` para oferecer mapas bem diferentes entre si."""
    rng = random.Random(seed)
    grid_labirinto = _gerar_labirinto(rows, cols_labirinto, rng)
    _adicionar_lacos(grid_labirinto, rng, rows, cols_labirinto, fracao=fracao_lacos)

    colunas_total = cols_labirinto + 1 + largura_sala_isolada + 1
    grid = [['#'] * colunas_total for _ in range(rows)]
    for r in range(rows):
        for c in range(cols_labirinto):
            grid[r][c] = grid_labirinto[r][c]

    # Sala isolada, sem nenhuma porta de acesso: usada para demonstrar que o
    # sistema detecta corretamente quando não existe caminho até o destino.
    # Posição/altura são relativas ao tamanho do mapa para funcionar em
    # qualquer um dos presets.
    col_sala = cols_labirinto + 1
    altura_sala = min(5, max(2, rows - 4))
    linha_inicio_sala = max(1, (rows - altura_sala) // 2)
    linha_fim_sala = min(rows - 1, linha_inicio_sala + altura_sala)
    for r in range(linha_inicio_sala, linha_fim_sala):
        for c in range(col_sala, col_sala + largura_sala_isolada):
            grid[r][c] = '.'

    floor_labirinto = [(r, c) for r in range(rows) for c in range(cols_labirinto)
                        if grid[r][c] != '#']

    dist0 = _bfs_distancias(grid, floor_labirinto[0], rows, colunas_total)
    ponto_a = max(dist0, key=dist0.get)
    dist1 = _bfs_distancias(grid, ponto_a, rows, colunas_total)
    ponto_b = max(dist1, key=dist1.get)
    inicio, objetivo = ponto_a, ponto_b

    pesos_terreno = [('.', 0.55), (':', 0.25), ('^', 0.12), ('~', 0.08)]
    letras, pesos = zip(*pesos_terreno)
    todas_celulas = [(r, c) for r in range(rows) for c in range(colunas_total)
                      if grid[r][c] != '#']
    for (r, c) in todas_celulas:
        if (r, c) not in (inicio, objetivo):
            grid[r][c] = rng.choices(letras, weights=pesos, k=1)[0]
        else:
            grid[r][c] = '.'

    sala_isolada_cels = {(r, c) for r in range(linha_inicio_sala, linha_fim_sala)
                          for c in range(col_sala, col_sala + largura_sala_isolada)}
    excluir = {inicio, objetivo} | sala_isolada_cels
    candidatas_recompensa = [p for p in floor_labirinto if p not in excluir]
    rng.shuffle(candidatas_recompensa)
    recompensas = sorted(candidatas_recompensa[:min(num_recompensas, len(candidatas_recompensa))])

    grid_strings = [''.join(row) for row in grid]
    return Ambiente(grid=grid_strings, inicio=inicio, objetivo=objetivo,
                     recompensas=recompensas)


def gerar_ambiente_preset(nome_preset: str) -> Ambiente:
    """Atalho para gerar um ambiente a partir de um dos formatos prontos em
    `PRESETS_LABIRINTO`."""
    return gerar_ambiente(**PRESETS_LABIRINTO[nome_preset])
