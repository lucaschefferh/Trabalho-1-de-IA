"""
Interface gráfica do trabalho: desenha o mapa, permite escolher o algoritmo
de busca, calcular a rota, animar o agente percorrendo-a, comparar os
algoritmos entre si e (o pedido explícito) mostrar a árvore de busca gerada
depois que o algoritmo termina.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from arvore import mostrar_janela_arvore
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

COR_FUNDO = "#1e1f26"
COR_PAINEL = "#262832"
COR_TEXTO = "#f2f2f2"
COR_SUBTEXTO = "#a9adba"
COR_ACENTO = "#ff8c42"
COR_CAMINHO = "#ff8c42"
COR_AGENTE = "#e63946"
COR_INICIO = "#3a86ff"
COR_OBJETIVO = "#2ecc71"
COR_RECOMPENSA = "#f2c14e"

TAMANHO_CELULA = 26


class Aplicacao(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Trabalho 1 — Navegação Autônoma por Busca em Grafo (UTFPR)")
        self.configure(bg=COR_FUNDO)
        self.resizable(False, False)

        self.preset_atual = PRESET_PADRAO
        self.ambiente: Ambiente = gerar_ambiente_preset(self.preset_atual)
        self.objetivo_padrao = self.ambiente.objetivo
        self.ultimo_resultado: ResultadoBusca | None = None
        self.resultados_comparacao: dict[str, ResultadoBusca] = {}
        self.animando = False
        self._ids_recompensa: dict[tuple[int, int], int] = {}
        self._id_agente: int | None = None

        self._configurar_estilo()
        self._montar_layout()
        self._desenhar_mapa()

    # ------------------------------------------------------------------ UI

    def _configurar_estilo(self) -> None:
        estilo = ttk.Style(self)
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass
        estilo.configure("TFrame", background=COR_PAINEL)
        estilo.configure("TLabel", background=COR_PAINEL, foreground=COR_TEXTO,
                          font=("Segoe UI", 10))
        estilo.configure("Titulo.TLabel", background=COR_FUNDO, foreground=COR_TEXTO,
                          font=("Segoe UI", 17, "bold"))
        estilo.configure("Subtitulo.TLabel", background=COR_FUNDO, foreground=COR_SUBTEXTO,
                          font=("Segoe UI", 10))
        estilo.configure("Secao.TLabel", background=COR_PAINEL, foreground=COR_ACENTO,
                          font=("Segoe UI", 11, "bold"))
        estilo.configure("Status.TLabel", background=COR_PAINEL, foreground=COR_TEXTO,
                          font=("Consolas", 10))
        estilo.configure("TButton", font=("Segoe UI", 10), padding=6)
        estilo.configure("Acento.TButton", font=("Segoe UI", 10, "bold"), padding=8)
        estilo.configure("TCombobox", padding=4)
        estilo.configure("Treeview", background="#2f3140", fieldbackground="#2f3140",
                          foreground=COR_TEXTO, rowheight=26, font=("Segoe UI", 9))
        estilo.configure("Treeview.Heading", background="#3a3d4d", foreground=COR_TEXTO,
                          font=("Segoe UI", 9, "bold"))
        estilo.map("Treeview", background=[("selected", COR_ACENTO)])

    def _montar_layout(self) -> None:
        cabecalho = tk.Frame(self, bg=COR_FUNDO)
        cabecalho.pack(fill="x", padx=16, pady=(14, 6))
        ttk.Label(cabecalho, text="Navegação Autônoma por Busca em Grafo",
                   style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(
            cabecalho,
            text="Fundamentos de Sistemas Inteligentes — Trabalho 1  |  "
                 "Largura · Profundidade · Gulosa · A* · Custo Uniforme",
            style="Subtitulo.TLabel",
        ).pack(anchor="w")

        corpo = tk.Frame(self, bg=COR_FUNDO)
        corpo.pack(fill="both", expand=True, padx=16, pady=(0, 14))

        # --- mapa (esquerda) ---
        bloco_mapa = tk.Frame(corpo, bg=COR_PAINEL, bd=0)
        bloco_mapa.pack(side="left", fill="both", padx=(0, 14))

        largura_px = self.ambiente.colunas * TAMANHO_CELULA
        altura_px = self.ambiente.linhas * TAMANHO_CELULA
        self.canvas = tk.Canvas(bloco_mapa, width=largura_px, height=altura_px,
                                 bg=COR_FUNDO, highlightthickness=0)
        self.canvas.pack(padx=10, pady=10)
        self.canvas.bind("<Button-1>", self._ao_clicar_no_mapa)

        self._montar_legenda(bloco_mapa)

        # --- painel de controle (direita) ---
        painel = tk.Frame(corpo, bg=COR_PAINEL)
        painel.pack(side="left", fill="both", expand=True)

        pad = {"padx": 14, "pady": 6}

        ttk.Label(painel, text="Formato do labirinto", style="Secao.TLabel").pack(
            anchor="w", **pad)
        self.combo_labirinto = ttk.Combobox(
            painel, values=list(PRESETS_LABIRINTO.keys()), state="readonly",
            font=("Segoe UI", 10))
        self.combo_labirinto.set(self.preset_atual)
        self.combo_labirinto.pack(fill="x", padx=14)
        ttk.Button(painel, text="Gerar Mapa", command=self._trocar_labirinto).pack(
            fill="x", padx=14, pady=(6, 0))

        ttk.Separator(painel).pack(fill="x", padx=14, pady=10)

        ttk.Label(painel, text="Algoritmo de busca", style="Secao.TLabel").pack(
            anchor="w", **pad)
        self.combo_algoritmo = ttk.Combobox(
            painel, values=list(ALGORITMOS.keys()), state="readonly",
            font=("Segoe UI", 10))
        self.combo_algoritmo.current(3)  # A*
        self.combo_algoritmo.pack(fill="x", padx=14)

        ttk.Button(painel, text="Calcular Rota", style="Acento.TButton",
                   command=self._calcular_rota).pack(fill="x", padx=14, pady=(10, 4))
        self.btn_animar = ttk.Button(painel, text="Animar Agente", state="disabled",
                                      command=self._animar_agente)
        self.btn_animar.pack(fill="x", padx=14, pady=4)
        self.btn_arvore = ttk.Button(painel, text="Mostrar Árvore de Busca",
                                      state="disabled", command=self._mostrar_arvore)
        self.btn_arvore.pack(fill="x", padx=14, pady=4)

        ttk.Separator(painel).pack(fill="x", padx=14, pady=10)

        ttk.Label(painel, text="Objetivo", style="Secao.TLabel").pack(anchor="w", **pad)
        ttk.Label(painel, text="Clique em uma célula do mapa para definir um\n"
                                "novo objetivo (útil para testar áreas sem saída).",
                   style="TLabel", wraplength=300, justify="left").pack(anchor="w", padx=14)
        ttk.Button(painel, text="Restaurar Objetivo Padrão",
                   command=self._restaurar_objetivo).pack(fill="x", padx=14, pady=(6, 4))

        ttk.Separator(painel).pack(fill="x", padx=14, pady=10)

        ttk.Label(painel, text="Comparativo entre algoritmos", style="Secao.TLabel").pack(
            anchor="w", **pad)
        ttk.Button(painel, text="Comparar Algoritmos (tempo médio)",
                   command=self._comparar_todos).pack(fill="x", padx=14, pady=(0, 6))

        colunas = ("custo", "recompensas", "saldo", "nos", "fronteira", "tempo")
        self.tabela = ttk.Treeview(painel, columns=colunas, show="tree headings",
                                    height=len(ALGORITMOS))
        self.tabela.heading("#0", text="Algoritmo")
        self.tabela.heading("custo", text="Custo")
        self.tabela.heading("recompensas", text="$")
        self.tabela.heading("saldo", text="Saldo")
        self.tabela.heading("nos", text="Expand.")
        self.tabela.heading("fronteira", text="Front.")
        self.tabela.heading("tempo", text="ms")
        self.tabela.column("#0", width=125)
        self.tabela.column("custo", width=45, anchor="center")
        self.tabela.column("recompensas", width=30, anchor="center")
        self.tabela.column("saldo", width=45, anchor="center")
        self.tabela.column("nos", width=55, anchor="center")
        self.tabela.column("fronteira", width=45, anchor="center")
        self.tabela.column("tempo", width=55, anchor="center")
        self.tabela.pack(fill="x", padx=14)
        self.tabela.bind("<Double-1>", self._ao_dar_duplo_clique_tabela)
        ttk.Label(painel, text=f"Saldo = {VALOR_RECOMPENSA} × $ − custo. Front. = pico de "
                                "nós na fronteira (memória). Duplo clique numa "
                                "linha abre a árvore de busca.",
                   style="TLabel", wraplength=300, justify="left").pack(
            anchor="w", padx=14, pady=(4, 0))

        ttk.Separator(painel).pack(fill="x", padx=14, pady=10)

        ttk.Label(painel, text="Status", style="Secao.TLabel").pack(anchor="w", **pad)
        self.rotulo_status = ttk.Label(painel, text="Escolha um algoritmo e clique em "
                                                      "\"Calcular Rota\".",
                                        style="Status.TLabel", wraplength=300,
                                        justify="left")
        self.rotulo_status.pack(anchor="w", padx=14, pady=(0, 10))

    def _montar_legenda(self, parent: tk.Widget) -> None:
        legenda = tk.Frame(parent, bg=COR_PAINEL)
        legenda.pack(fill="x", padx=10, pady=(0, 10))
        itens = [
            ("Parede", CORES_TERRENO['#']),
            *[(NOMES_TERRENO[t], CORES_TERRENO[t]) for t in ".:^~"],
        ]
        for i, (texto, cor) in enumerate(itens):
            bloco = tk.Frame(legenda, bg=COR_PAINEL)
            bloco.grid(row=i // 3, column=i % 3, sticky="w", padx=6, pady=2)
            tk.Canvas(bloco, width=14, height=14, bg=cor, highlightthickness=1,
                      highlightbackground="#555").pack(side="left", padx=(0, 6))
            tk.Label(bloco, text=texto, bg=COR_PAINEL, fg=COR_TEXTO,
                     font=("Segoe UI", 8)).pack(side="left")

    # --------------------------------------------------------------- Mapa

    def _celula_para_pixels(self, pos: tuple[int, int]) -> tuple[float, float]:
        r, c = pos
        return c * TAMANHO_CELULA, r * TAMANHO_CELULA

    def _desenhar_mapa(self) -> None:
        self.canvas.delete("all")
        self._ids_recompensa.clear()
        ambiente = self.ambiente

        for r in range(ambiente.linhas):
            for c in range(ambiente.colunas):
                terreno = ambiente.grid[r][c]
                x0, y0 = c * TAMANHO_CELULA, r * TAMANHO_CELULA
                x1, y1 = x0 + TAMANHO_CELULA, y0 + TAMANHO_CELULA
                cor = CORES_TERRENO[terreno]
                self.canvas.create_rectangle(x0, y0, x1, y1, fill=cor, outline="#14151a",
                                              width=1)

        for pos in ambiente.recompensas:
            self._desenhar_recompensa(pos)

        self._desenhar_marcador_inicio(ambiente.inicio)
        self._desenhar_marcador_objetivo(ambiente.objetivo)

    def _desenhar_recompensa(self, pos: tuple[int, int]) -> None:
        x0, y0 = self._celula_para_pixels(pos)
        cx, cy = x0 + TAMANHO_CELULA / 2, y0 + TAMANHO_CELULA / 2
        raio = TAMANHO_CELULA * 0.32
        oval = self.canvas.create_oval(cx - raio, cy - raio, cx + raio, cy + raio,
                                        fill=COR_RECOMPENSA, outline="#8a6d1a", width=1)
        texto = self.canvas.create_text(cx, cy, text="$", fill="#4a3900",
                                         font=("Segoe UI", 10, "bold"))
        self._ids_recompensa[pos] = (oval, texto)

    def _desenhar_marcador_inicio(self, pos: tuple[int, int]) -> None:
        x0, y0 = self._celula_para_pixels(pos)
        cx, cy = x0 + TAMANHO_CELULA / 2, y0 + TAMANHO_CELULA / 2
        raio = TAMANHO_CELULA * 0.4
        self.canvas.create_oval(cx - raio, cy - raio, cx + raio, cy + raio,
                                 fill=COR_INICIO, outline="white", width=1.5,
                                 tags="marcador_inicio")
        self.canvas.create_text(cx, cy - TAMANHO_CELULA * 0.75, text="Início",
                                 fill="white", font=("Segoe UI", 8, "bold"),
                                 tags="marcador_inicio")

    def _desenhar_marcador_objetivo(self, pos: tuple[int, int]) -> None:
        x0, y0 = self._celula_para_pixels(pos)
        cx, cy = x0 + TAMANHO_CELULA / 2, y0 + TAMANHO_CELULA / 2
        pontos = self._pontos_estrela(cx, cy, TAMANHO_CELULA * 0.44, TAMANHO_CELULA * 0.2)
        self.canvas.create_polygon(pontos, fill=COR_OBJETIVO, outline="white", width=1.2,
                                    tags="marcador_objetivo")
        self.canvas.create_text(cx, cy - TAMANHO_CELULA * 0.75, text="Prêmio",
                                 fill="white", font=("Segoe UI", 8, "bold"),
                                 tags="marcador_objetivo")

    @staticmethod
    def _pontos_estrela(cx: float, cy: float, r_ext: float, r_int: float) -> list[float]:
        import math
        pontos = []
        for i in range(10):
            ang = math.pi / 2 + i * math.pi / 5
            r = r_ext if i % 2 == 0 else r_int
            pontos.extend([cx + r * math.cos(ang), cy - r * math.sin(ang)])
        return pontos

    def _desenhar_caminho(self, caminho: list[tuple[int, int]]) -> None:
        self.canvas.delete("caminho")
        for pos in caminho:
            x0, y0 = self._celula_para_pixels(pos)
            x1, y1 = x0 + TAMANHO_CELULA, y0 + TAMANHO_CELULA
            self.canvas.create_rectangle(x0 + 3, y0 + 3, x1 - 3, y1 - 3, outline=COR_CAMINHO,
                                          width=2, tags="caminho")

    # ---------------------------------------------------------- Interação

    def _ao_clicar_no_mapa(self, evento: tk.Event) -> None:
        if self.animando:
            return
        c = evento.x // TAMANHO_CELULA
        r = evento.y // TAMANHO_CELULA
        pos = (r, c)
        if self.ambiente.eh_parede(pos):
            return
        if pos == self.ambiente.inicio:
            return
        self.ambiente.objetivo = pos
        self._limpar_resultado()
        self._desenhar_mapa()
        self.rotulo_status.configure(
            text=f"Novo objetivo definido em {pos}. Clique em \"Calcular Rota\".")

    def _restaurar_objetivo(self) -> None:
        self.ambiente.objetivo = self.objetivo_padrao
        self._limpar_resultado()
        self._desenhar_mapa()
        self.rotulo_status.configure(text="Objetivo padrão restaurado.")

    def _trocar_labirinto(self) -> None:
        if self.animando:
            return
        nome_preset = self.combo_labirinto.get()
        if not nome_preset:
            return
        self.preset_atual = nome_preset
        self.ambiente = gerar_ambiente_preset(nome_preset)
        self.objetivo_padrao = self.ambiente.objetivo

        self._limpar_resultado()
        self.resultados_comparacao.clear()
        for item in self.tabela.get_children():
            self.tabela.delete(item)

        largura_px = self.ambiente.colunas * TAMANHO_CELULA
        altura_px = self.ambiente.linhas * TAMANHO_CELULA
        self.canvas.config(width=largura_px, height=altura_px)
        self._desenhar_mapa()
        self.geometry("")  # deixa a janela recalcular o tamanho para o novo mapa

        vertices = sum(1 for r in range(self.ambiente.linhas) for c in range(self.ambiente.colunas)
                        if not self.ambiente.eh_parede((r, c)))
        self.rotulo_status.configure(
            text=f"Novo labirinto: \"{nome_preset}\" ({self.ambiente.linhas}x"
                 f"{self.ambiente.colunas}, {vertices} vértices andáveis, "
                 f"{len(self.ambiente.recompensas)} recompensas).")

    def _limpar_resultado(self) -> None:
        self.ultimo_resultado = None
        self.btn_animar.configure(state="disabled")
        self.btn_arvore.configure(state="disabled")
        self.canvas.delete("caminho")

    # ------------------------------------------------------------ Ações

    def _calcular_rota(self) -> None:
        if self.animando:
            return
        nome = self.combo_algoritmo.get()
        algoritmo = ALGORITMOS[nome]
        resultado = algoritmo(self.ambiente)
        self.ultimo_resultado = resultado
        self._desenhar_mapa()

        if not resultado.encontrou_caminho:
            self.btn_animar.configure(state="disabled")
            self.btn_arvore.configure(state="normal")
            self.rotulo_status.configure(
                text=f"[{resultado.nome}] Nenhum caminho encontrado até o objetivo "
                     f"{self.ambiente.objetivo}.\nNós expandidos: {resultado.nos_expandidos}  |  "
                     f"Pico da fronteira: {resultado.max_fronteira}  |  "
                     f"Tempo: {resultado.tempo_execucao_s * 1000:.2f} ms")
            messagebox.showwarning(
                "Caminho não encontrado",
                f"O algoritmo \"{resultado.nome}\" não encontrou nenhum caminho até "
                f"{self.ambiente.objetivo}.\n\nO destino pode estar isolado por paredes "
                f"(sem nenhuma porta de acesso) ou dentro de um beco sem saída.")
            return

        self._desenhar_caminho(resultado.caminho)
        self.btn_animar.configure(state="normal")
        self.btn_arvore.configure(state="normal")
        self.rotulo_status.configure(
            text=f"[{resultado.nome}]\n"
                 f"Custo total do caminho: {resultado.custo_total}\n"
                 f"Recompensas coletadas: {len(resultado.recompensas_coletadas)} de "
                 f"{len(self.ambiente.recompensas)}\n"
                 f"Saldo ({VALOR_RECOMPENSA} × $ − custo): {resultado.saldo}\n"
                 f"Nós expandidos: {resultado.nos_expandidos}  |  gerados: "
                 f"{resultado.nos_gerados}\n"
                 f"Pico da fronteira: {resultado.max_fronteira}\n"
                 f"Tempo de execução: {resultado.tempo_execucao_s * 1000:.2f} ms")

    def _animar_agente(self) -> None:
        if self.animando or not self.ultimo_resultado or not self.ultimo_resultado.caminho:
            return
        self.animando = True
        self.btn_animar.configure(state="disabled")
        caminho = self.ultimo_resultado.caminho
        recompensas_no_caminho = set(self.ultimo_resultado.recompensas_coletadas)

        cx0, cy0 = self._celula_para_pixels(caminho[0])
        cx0 += TAMANHO_CELULA / 2
        cy0 += TAMANHO_CELULA / 2
        raio = TAMANHO_CELULA * 0.32
        self._id_agente = self._desenhar_agente(cx0, cy0, raio)

        estado = {"indice": 0, "custo": 0, "coletadas": 0}

        def passo() -> None:
            i = estado["indice"]
            pos = caminho[i]
            if i > 0:
                estado["custo"] += self.ambiente.custo_aresta(caminho[i - 1], pos)
            if pos in recompensas_no_caminho and pos in self._ids_recompensa:
                for item_id in self._ids_recompensa[pos]:
                    self.canvas.delete(item_id)
                del self._ids_recompensa[pos]
                estado["coletadas"] += 1

            x0, y0 = self._celula_para_pixels(pos)
            cx, cy = x0 + TAMANHO_CELULA / 2, y0 + TAMANHO_CELULA / 2
            self.canvas.coords(self._id_agente[0], cx - raio, cy - raio, cx + raio, cy + raio)
            self.canvas.coords(self._id_agente[1], cx - raio * 0.35, cy - raio * 0.15,
                                cx - raio * 0.1, cy - raio * 0.15 + raio * 0.22)
            self.canvas.coords(self._id_agente[2], cx + raio * 0.1, cy - raio * 0.15,
                                cx + raio * 0.35, cy - raio * 0.15 + raio * 0.22)
            self.canvas.coords(self._id_agente[3], cx - raio * 0.35, cy + raio * 0.1,
                                cx + raio * 0.35, cy + raio * 0.5)

            self.rotulo_status.configure(
                text=f"[{self.ultimo_resultado.nome}] Animando... passo {i + 1}/{len(caminho)}\n"
                     f"Custo acumulado: {estado['custo']}\n"
                     f"Recompensas coletadas até agora: {estado['coletadas']}")

            if i + 1 < len(caminho):
                estado["indice"] += 1
                self.after(140, passo)
            else:
                self.animando = False
                self.btn_animar.configure(state="normal")
                self.rotulo_status.configure(
                    text=f"[{self.ultimo_resultado.nome}] Agente chegou ao objetivo!\n"
                         f"Custo total: {estado['custo']}\n"
                         f"Recompensas coletadas: {estado['coletadas']}\n"
                         f"Saldo: {self.ultimo_resultado.saldo}")

        passo()

    def _desenhar_agente(self, cx: float, cy: float, raio: float) -> tuple[int, int, int, int]:
        corpo = self.canvas.create_oval(cx - raio, cy - raio, cx + raio, cy + raio,
                                         fill=COR_AGENTE, outline="white", width=1.5,
                                         tags="agente")
        olho_e = self.canvas.create_oval(cx - raio * 0.35, cy - raio * 0.15,
                                          cx - raio * 0.1, cy - raio * 0.15 + raio * 0.22,
                                          fill="white", outline="", tags="agente")
        olho_d = self.canvas.create_oval(cx + raio * 0.1, cy - raio * 0.15,
                                          cx + raio * 0.35, cy - raio * 0.15 + raio * 0.22,
                                          fill="white", outline="", tags="agente")
        boca = self.canvas.create_arc(cx - raio * 0.35, cy + raio * 0.1,
                                       cx + raio * 0.35, cy + raio * 0.5,
                                       start=200, extent=140, style="arc",
                                       outline="white", width=1.5, tags="agente")
        return corpo, olho_e, olho_d, boca

    def _mostrar_arvore(self) -> None:
        if self.ultimo_resultado is None:
            return
        mostrar_janela_arvore(self, self.ultimo_resultado)

    def _comparar_todos(self) -> None:
        if self.animando:
            return
        for item in self.tabela.get_children():
            self.tabela.delete(item)
        self.resultados_comparacao.clear()

        self.rotulo_status.configure(text="Comparando algoritmos...")
        self.update_idletasks()
        for nome, algoritmo in ALGORITMOS.items():
            resultado = executar_com_tempo_medio(algoritmo, self.ambiente)
            self.resultados_comparacao[nome] = resultado
            achou = resultado.encontrou_caminho
            self.tabela.insert("", "end", iid=nome, text=nome, values=(
                resultado.custo_total if achou else "sem caminho",
                len(resultado.recompensas_coletadas) if achou else "—",
                resultado.saldo if achou else "—",
                resultado.nos_expandidos, resultado.max_fronteira,
                f"{resultado.tempo_execucao_s * 1000:.2f}"))

        self.rotulo_status.configure(
            text=f"Comparação concluída ({len(ALGORITMOS)} algoritmos).\n"
                 "Tempo = média de várias execuções de cada algoritmo.\n"
                 "Dê duplo clique numa linha da tabela para ver a árvore de busca "
                 "daquele algoritmo.")

    def _ao_dar_duplo_clique_tabela(self, _evento: tk.Event) -> None:
        selecao = self.tabela.selection()
        if not selecao:
            return
        nome = selecao[0]
        resultado = self.resultados_comparacao.get(nome)
        if resultado is None:
            return
        self.ultimo_resultado = resultado
        if resultado.encontrou_caminho:
            self._desenhar_mapa()
            self._desenhar_caminho(resultado.caminho)
            self.btn_animar.configure(state="normal")
        self.btn_arvore.configure(state="normal")
        mostrar_janela_arvore(self, resultado)


def executar() -> None:
    app = Aplicacao()
    app.mainloop()
