# Trabalho 1 — Navegação Autônoma por Busca em Grafo

Agente que atravessa um labirinto 2D com terrenos de custos diferentes, coleta
recompensas (`$`) e chega ao prêmio final usando **Busca em Largura**, **Busca em
Profundidade**, **Busca Gulosa** e **A\***.

## Como rodar

### Opção 1 — Docker (recomendado, funciona igual em qualquer máquina)

```bash
docker build -t trabalho1-ia .
docker run --rm -p 8501:8501 trabalho1-ia
```

Depois abra **http://localhost:8501** no navegador.

### Opção 2 — Local (Streamlit)

Requer Python 3.9+.

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app_streamlit.py
```

Na primeira execução o Streamlit pode pedir um e-mail no terminal — basta
apertar Enter.

## Estrutura

| Arquivo | Conteúdo |
|---|---|
| `mapa.py` | Geração do labirinto, terrenos, recompensas e presets de mapa |
| `busca.py` | Algoritmos de busca, heurística e métricas |
| `arvore.py` | Desenho da árvore de busca gerada por cada algoritmo |
| `app_streamlit.py` | Interface web (Streamlit) |

## Modelagem

- **Grafo:** cada célula andável do grid é um vértice, ligado aos vizinhos
  ortogonais. Paredes (`#`) não são vértices.
- **Custo de uma aresta:** custo do terreno de destino — sólido 1, arenoso 4,
  rochoso 10, pântano 20.
- **Mapas:** 5 presets de labirinto (Padrão, Compacto, Grande, Denso e Aberto),
  todos determinísticos (seed fixa), com pelo menos 30 vértices e 5 recompensas.

### Buscas cegas (Largura e Profundidade)

O estado é só a posição. O agente coleta as recompensas que estiverem nos
vértices do caminho encontrado até o prêmio.

### Buscas informadas (Gulosa e A\*)

Para o algoritmo conseguir decidir **se compensa desviar** da rota para pegar
uma recompensa, isso faz parte do próprio problema:

- **Estado:** `(posição, recompensas já coletadas)` — as recompensas são uma
  máscara de bits.
- **Custo total:** `J = custo do percurso + V × (recompensas deixadas para trás)`,
  com `V = 15` por padrão (`VALOR_RECOMPENSA` em `busca.py`).
- Minimizar `J` equivale a maximizar o **saldo** `= V × recompensas − custo`.
  Um desvio compensa exatamente quando custa menos que `V`.
- **`V` é ajustável.** O enunciado não define o valor de uma recompensa, então é um
  parâmetro de modelagem: o slider *Valor da recompensa* (0 a 100) muda `V` na
  heurística, na prioridade da busca e no saldo. `V` baixo faz o A\* ignorar as
  recompensas; `V` alto faz o agente buscá-las, aceitando rotas mais caras. As
  buscas cegas não dependem de `V` (só o saldo muda).

**Heurística.** A Gulosa e o A\* usam a mesma. Seja `d` a distância de Manhattan
(nunca superestima, pois o terreno mais barato custa 1). Para cada recompensa `r`
ainda não coletada:

```
desvio(p, r) = d(p, r) + d(r, G) − d(p, G)
c(p, r)      = min(V, desvio(p, r))      # desviar ou abandonar: o mais barato
h(p, M)      = d(p, G) + max_r c(p, r)
```

*Por que é admissível:* para cada `r`, a solução ótima ou passa por `r` (custo
≥ `d(p,G) + desvio`) ou não passa (custo ≥ `d(p,G) + V`); logo custa pelo menos
`d(p,G) + c(p,r)` para todo `r`, e portanto pelo menos o máximo. Assim, o A\*
devolve a rota ótima em `J`. A heurística não é consistente, então o A\* reabre
estados quando encontra um caminho mais barato até eles.

A diferença entre Gulosa e A\* está só na prioridade da fronteira: o A\* ordena
por `g + h`; a Gulosa, só por `h`, sem olhar o custo já gasto.

A Gulosa para assim que gera um estado no prêmio. Se esperasse o estado final
sair da fila (com prioridade `V × faltando`), continuaria buscando combinações
melhores de recompensas e viraria uma busca praticamente exaustiva.

### Métricas do comparativo

- **Nós expandidos** e **nós gerados**;
- **Pico da fronteira** — maior número de nós aguardando expansão ao mesmo
  tempo (uso de memória);
- **Tempo** — média de até 30 execuções (limitado a ~1 s por algoritmo), já
  que uma medição isolada abaixo de 1 ms é dominada por ruído;
- **Custo**, **recompensas coletadas** e **saldo**.
