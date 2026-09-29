# Trabalho 1 — Navegação Autônoma por Busca em Grafo

Agente que atravessa um labirinto 2D com terrenos de custos diferentes, coleta
recompensas (`$`) e chega ao prêmio final usando **Busca em Largura**, **Busca em
Profundidade**, **Busca Gulosa**, **A\*** e, como referência extra, **Custo
Uniforme (Dijkstra)**.

## Como rodar

### Opção 1 — Docker (recomendado, funciona igual em qualquer máquina)

```bash
docker build -t trabalho1-ia .
docker run --rm -p 8501:8501 trabalho1-ia
```

Depois abra **http://localhost:8501** no navegador.

### Opção 2 — Local, versão web (Streamlit)

Requer Python 3.9+.

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app_streamlit.py
```

Na primeira execução o Streamlit pode pedir um e-mail no terminal — basta
apertar Enter.

### Opção 3 — Local, versão desktop (Tkinter)

Com o mesmo ambiente da opção 2:

```bash
python main.py
```

> **macOS:** o Python que vem com o sistema (`/usr/bin/python3`) usa Tk 8.5, que
> abre a janela **em branco** nas versões recentes do macOS. Use um Python
> instalado pelo [python.org](https://www.python.org/downloads/) (já vem com
> Tk 8.6) ou a versão web/Docker.
>
> **Linux:** pode ser necessário instalar o Tk (`sudo apt install python3-tk`).

O Docker roda apenas a versão web: janelas Tkinter dentro de container exigem
configurar servidor gráfico (X11), o que não vale a pena aqui.

## Estrutura

| Arquivo | Conteúdo |
|---|---|
| `mapa.py` | Geração do labirinto, terrenos, recompensas, sala isolada e presets de mapa |
| `busca.py` | Algoritmos de busca, heurísticas e métricas |
| `arvore.py` | Desenho da árvore de busca gerada por cada algoritmo |
| `interface.py` / `main.py` | Interface desktop (Tkinter) |
| `app_streamlit.py` | Interface web (Streamlit) |

## Modelagem

- **Grafo:** cada célula andável do grid é um vértice, ligado aos vizinhos
  ortogonais. Paredes (`#`) não são vértices.
- **Custo de uma aresta:** custo do terreno de destino — sólido 1, arenoso 4,
  rochoso 10, pântano 20.
- **Sala isolada:** todo mapa tem uma sala sem portas com uma recompensa
  inalcançável. O preset **"Prêmio inalcançável"** coloca o próprio prêmio lá
  dentro para demonstrar a detecção de "não existe caminho" (a fronteira se
  esgota sem atingir o objetivo).

### Buscas cegas (Largura e Profundidade)

O estado é só a posição. O agente coleta as recompensas que estiverem nos
vértices do caminho encontrado até o prêmio.

### Buscas informadas (Gulosa, A\*, Custo Uniforme)

Para o algoritmo conseguir decidir **se compensa desviar** da rota para pegar
uma recompensa, isso faz parte do próprio problema:

- **Estado:** `(posição, recompensas já coletadas)` — as recompensas são uma
  máscara de bits.
- **Custo total:** `J = custo do percurso + V × (recompensas deixadas para trás)`,
  com `V = 15` (`VALOR_RECOMPENSA` em `busca.py`).
- Minimizar `J` equivale a maximizar o **saldo** `= V × recompensas − custo`.
  Um desvio compensa exatamente quando custa menos que `V`.

**Heurística.** Seja `d` a distância de Manhattan (nunca superestima, pois o
terreno mais barato custa 1). Para cada recompensa `r` ainda não coletada:

```
desvio(p, r) = d(p, r) + d(r, G) − d(p, G)
c(p, r)      = min(V, desvio(p, r))      # desviar ou abandonar: o mais barato
```

| Algoritmo | Heurística | Propriedade |
|---|---|---|
| A\* | `d(p, G) + max_r c(p, r)` | **Admissível** → rota ótima em `J` |
| Gulosa | `d(p, G) + Σ_r c(p, r)` | Mais agressiva, não admissível |
| Custo Uniforme | `0` | Ótimo; referência para medir o ganho da heurística |

*Por que a do A\* é admissível:* para cada `r`, a solução ótima ou passa por
`r` (custo ≥ `d(p,G) + desvio`) ou não passa (custo ≥ `d(p,G) + V`); logo
custa pelo menos `d(p,G) + c(p,r)` para todo `r`, e portanto pelo menos o
máximo. A heurística não é consistente, então o A\* reabre estados quando
encontra um caminho mais barato até eles.

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

## Mudanças desta versão (branch `heuristica-recompensas`)

**Correção principal — recompensas nas buscas informadas.** Na versão anterior
o estado era só a posição e a heurística subtraía um "bônus" das recompensas
próximas. Como a heurística era admissível, o A\* sempre devolvia o caminho de
menor custo até o prêmio, **ignorando as recompensas**: o bônus só mudava a
ordem de expansão, nunca a rota (ex.: um `$` a 3 passos de desvio, valendo 15,
não era coletado). Além disso, a lista de recompensas restantes nunca era
atualizada durante a busca. Agora as buscas informadas usam o espaço de estados
`(posição, recompensas)` com a penalidade `V` descrita acima.

Resultado no mapa "Aberto": o A\* passou de 2 para 3 recompensas (custo 128,
saldo −83, o melhor entre todos os algoritmos).

**Outras mudanças**

- Novo algoritmo de referência: **Custo Uniforme**.
- Novas métricas: nós gerados, pico da fronteira e saldo.
- Tempo do comparativo passou a ser a média de várias execuções.
- A Gulosa usa conjunto de fechados clássico (antes reabria nós pelo custo
  `g`, que ela não deveria considerar).
- Novo preset de mapa **"Prêmio inalcançável"** e uma recompensa inalcançável
  na sala isolada de todos os mapas.
- Árvore de busca adaptada aos estados `(posição, recompensas)` e desenhada
  em lote (as árvores do A\* podem ter dezenas de milhares de nós).
- `arvore.py` importa o Tkinter só ao abrir a janela, para a versão web rodar
  em ambientes sem Tk (como o container Docker).
- `requirements.txt`: Streamlit mínimo passou para 1.50, versão testada (o app usa
  `width="stretch"`, que não existe em versões antigas).
- Adicionados `Dockerfile`, `.dockerignore`, `.gitignore` e este README.
