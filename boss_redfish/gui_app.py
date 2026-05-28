from __future__ import annotations

import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .acquiredp import AcquiredpCatalog, Device, Variable, filter_devices, filter_variables, parse_acquiredp
from .client import RedfishClient
from .discovery import BossUrls, diagnose_boss, fetch_text, normalize_boss_urls
from .gui_core import (
    DEFAULT_POLLING_MS,
    parse_polling_ms,
    polling_is_below_recommended,
    reading_table_rows,
    template_preview_rows,
)
from .template import build_sensor_definitions, chassis_id_for_device, create_generic_template_archive
from .web_import import manual_import_steps


DEFAULT_REDFISH_PASSWORD = ""


class RedfishWizardApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("BOSS Redfish Wizard")
        self.geometry("1120x760")
        self.minsize(980, 650)

        self.urls: BossUrls | None = None
        self.catalog: AcquiredpCatalog | None = None
        self.visible_devices: list[Device] = []
        self.current_device: Device | None = None
        self.visible_variables: list[Variable] = []
        self.selected_variables: list[Variable] = []
        self.generated_zip: Path | None = None
        self._polling_active = False
        self._polling_inflight = False
        self._polling_after_id: str | None = None
        self._polling_client: RedfishClient | None = None

        self.boss_url_var = tk.StringVar(value="")
        self.web_user_var = tk.StringVar(value="")
        self.redfish_password_var = tk.StringVar(value=DEFAULT_REDFISH_PASSWORD)
        self.device_filter_var = tk.StringVar(value="7")
        self.variable_filter_var = tk.StringVar(value="temp")
        self.output_zip_var = tk.StringVar(value=str(Path("dist") / "redfish_template_gui.zip"))
        self.polling_ms_var = tk.StringVar(value=str(DEFAULT_POLLING_MS))
        self.polling_status_var = tk.StringVar(value="Polling parado.")
        self.status_var = tk.StringVar(value="Pronto.")

        self._build_style()
        self._build_layout()

    def _build_style(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 15, "bold"))
        style.configure("Section.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("Status.TLabel", padding=(10, 7))
        style.configure("Action.TButton", padding=(12, 7))

    def _build_layout(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(root)
        header.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(header, text="BOSS Redfish Wizard", style="Title.TLabel").pack(side=tk.LEFT)
        ttk.Label(header, textvariable=self.status_var, style="Status.TLabel").pack(side=tk.RIGHT)

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.connection_tab = ttk.Frame(self.notebook, padding=12)
        self.selection_tab = ttk.Frame(self.notebook, padding=12)
        self.template_tab = ttk.Frame(self.notebook, padding=12)
        self.reading_tab = ttk.Frame(self.notebook, padding=12)

        self.notebook.add(self.connection_tab, text="1. Conexao")
        self.notebook.add(self.selection_tab, text="2. Controlador")
        self.notebook.add(self.template_tab, text="3. Template")
        self.notebook.add(self.reading_tab, text="4. Leitura")

        self._build_connection_tab()
        self._build_selection_tab()
        self._build_template_tab()
        self._build_reading_tab()

    def _build_connection_tab(self) -> None:
        form = ttk.Frame(self.connection_tab)
        form.pack(fill=tk.X)
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="URL do BOSS").grid(row=0, column=0, sticky=tk.W, pady=4)
        ttk.Entry(form, textvariable=self.boss_url_var).grid(row=0, column=1, sticky=tk.EW, padx=(8, 0), pady=4)

        ttk.Label(form, text="Usuario web").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Entry(form, textvariable=self.web_user_var, width=24).grid(row=1, column=1, sticky=tk.W, padx=(8, 0), pady=4)

        ttk.Label(form, text="Senha Redfish admin").grid(row=2, column=0, sticky=tk.W, pady=4)
        ttk.Entry(form, textvariable=self.redfish_password_var, width=24, show="*").grid(
            row=2, column=1, sticky=tk.W, padx=(8, 0), pady=4
        )

        actions = ttk.Frame(self.connection_tab)
        actions.pack(fill=tk.X, pady=10)
        ttk.Button(actions, text="Diagnosticar", style="Action.TButton", command=self.run_diagnose).pack(side=tk.LEFT)
        ttk.Button(actions, text="Carregar controladores", style="Action.TButton", command=self.load_catalog).pack(
            side=tk.LEFT, padx=8
        )

        ttk.Label(self.connection_tab, text="Resultado", style="Section.TLabel").pack(anchor=tk.W, pady=(14, 4))
        self.diagnostic_text = tk.Text(self.connection_tab, height=18, wrap=tk.WORD)
        self.diagnostic_text.pack(fill=tk.BOTH, expand=True)
        self._set_text(
            self.diagnostic_text,
            "Use Diagnosticar para validar BOSS web, acquiredp e Redfish.\n"
            "Depois use Carregar controladores para preencher a proxima tela.",
        )

    def _build_selection_tab(self) -> None:
        self.selection_tab.columnconfigure(0, weight=1)
        self.selection_tab.columnconfigure(1, weight=1)
        self.selection_tab.rowconfigure(1, weight=1)

        left_top = ttk.Frame(self.selection_tab)
        left_top.grid(row=0, column=0, sticky=tk.EW, padx=(0, 8))
        left_top.columnconfigure(1, weight=1)
        ttk.Label(left_top, text="Filtro controlador").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(left_top, textvariable=self.device_filter_var).grid(row=0, column=1, sticky=tk.EW, padx=8)
        ttk.Button(left_top, text="Filtrar", command=self.refresh_devices).grid(row=0, column=2)

        device_frame = ttk.Frame(self.selection_tab)
        device_frame.grid(row=1, column=0, sticky=tk.NSEW, padx=(0, 8), pady=8)
        device_frame.rowconfigure(0, weight=1)
        device_frame.columnconfigure(0, weight=1)
        self.device_list = tk.Listbox(device_frame, height=18, exportselection=False)
        self.device_list.grid(row=0, column=0, sticky=tk.NSEW)
        device_scroll = ttk.Scrollbar(device_frame, orient=tk.VERTICAL, command=self.device_list.yview)
        device_scroll.grid(row=0, column=1, sticky=tk.NS)
        self.device_list.configure(yscrollcommand=device_scroll.set)
        self.device_list.bind("<<ListboxSelect>>", lambda _event: self.select_device_from_list())

        right_top = ttk.Frame(self.selection_tab)
        right_top.grid(row=0, column=1, sticky=tk.EW)
        right_top.columnconfigure(1, weight=1)
        ttk.Label(right_top, text="Filtro variavel").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(right_top, textvariable=self.variable_filter_var).grid(row=0, column=1, sticky=tk.EW, padx=8)
        ttk.Button(right_top, text="Filtrar", command=self.refresh_variables).grid(row=0, column=2)

        variable_frame = ttk.Frame(self.selection_tab)
        variable_frame.grid(row=1, column=1, sticky=tk.NSEW, pady=8)
        variable_frame.rowconfigure(0, weight=1)
        variable_frame.columnconfigure(0, weight=1)
        self.variable_list = tk.Listbox(variable_frame, height=18, selectmode=tk.EXTENDED, exportselection=False)
        self.variable_list.grid(row=0, column=0, sticky=tk.NSEW)
        variable_scroll = ttk.Scrollbar(variable_frame, orient=tk.VERTICAL, command=self.variable_list.yview)
        variable_scroll.grid(row=0, column=1, sticky=tk.NS)
        self.variable_list.configure(yscrollcommand=variable_scroll.set)

        selection_actions = ttk.Frame(self.selection_tab)
        selection_actions.grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=(2, 8))
        ttk.Button(selection_actions, text="Adicionar variaveis selecionadas", command=self.add_selected_variables).pack(
            side=tk.LEFT
        )
        ttk.Button(selection_actions, text="Limpar selecao", command=self.clear_selected_variables).pack(side=tk.LEFT, padx=8)
        ttk.Button(selection_actions, text="Atualizar previa", command=self.refresh_template_preview).pack(side=tk.LEFT)

        ttk.Label(self.selection_tab, text="Variaveis escolhidas", style="Section.TLabel").grid(
            row=3, column=0, columnspan=2, sticky=tk.W
        )
        self.selected_tree = ttk.Treeview(self.selection_tab, columns=("code", "group", "kind"), show="headings", height=6)
        self.selected_tree.heading("code", text="Codigo BOSS")
        self.selected_tree.heading("group", text="Grupo")
        self.selected_tree.heading("kind", text="Tipo")
        self.selected_tree.grid(row=4, column=0, columnspan=2, sticky=tk.NSEW)
        self.selection_tab.rowconfigure(4, weight=1)

    def _build_template_tab(self) -> None:
        self.template_tab.rowconfigure(2, weight=1)
        self.template_tab.columnconfigure(0, weight=1)

        output_frame = ttk.Frame(self.template_tab)
        output_frame.grid(row=0, column=0, sticky=tk.EW)
        output_frame.columnconfigure(1, weight=1)
        ttk.Label(output_frame, text="Arquivo .zip").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(output_frame, textvariable=self.output_zip_var).grid(row=0, column=1, sticky=tk.EW, padx=8)
        ttk.Button(output_frame, text="Escolher", command=self.choose_output_zip).grid(row=0, column=2)

        actions = ttk.Frame(self.template_tab)
        actions.grid(row=1, column=0, sticky=tk.EW, pady=8)
        ttk.Button(actions, text="Gerar template", style="Action.TButton", command=self.generate_template).pack(side=tk.LEFT)
        ttk.Button(actions, text="Instrucoes de importacao", command=self.show_manual_import).pack(side=tk.LEFT, padx=8)

        self.preview_tree = ttk.Treeview(
            self.template_tab,
            columns=("name", "variable", "resource", "placeholder"),
            show="headings",
            height=14,
        )
        self.preview_tree.heading("name", text="Nome")
        self.preview_tree.heading("variable", text="Codigo BOSS")
        self.preview_tree.heading("resource", text="ID Redfish")
        self.preview_tree.heading("placeholder", text="Placeholder")
        self.preview_tree.column("name", width=170)
        self.preview_tree.column("variable", width=180)
        self.preview_tree.column("resource", width=220)
        self.preview_tree.column("placeholder", width=330)
        self.preview_tree.grid(row=2, column=0, sticky=tk.NSEW)

        ttk.Label(self.template_tab, text="Importacao manual", style="Section.TLabel").grid(row=3, column=0, sticky=tk.W, pady=(8, 4))
        self.import_text = tk.Text(self.template_tab, height=8, wrap=tk.WORD)
        self.import_text.grid(row=4, column=0, sticky=tk.EW)
        self._set_text(self.import_text, "Gere o template para ver o passo a passo de importacao.")

    def _build_reading_tab(self) -> None:
        self.reading_tab.rowconfigure(1, weight=1)
        self.reading_tab.columnconfigure(0, weight=1)

        actions = ttk.Frame(self.reading_tab)
        actions.grid(row=0, column=0, sticky=tk.EW)
        ttk.Button(actions, text="Ler variaveis selecionadas", style="Action.TButton", command=self.read_selected_values).pack(
            side=tk.LEFT
        )
        ttk.Button(actions, text="Iniciar polling", style="Action.TButton", command=self.start_polling).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(actions, text="Parar", command=self.stop_polling).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(actions, text="Polling time").pack(side=tk.LEFT, padx=(18, 4))
        ttk.Entry(actions, textvariable=self.polling_ms_var, width=8).pack(side=tk.LEFT)
        ttk.Label(actions, text="ms").pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(actions, textvariable=self.polling_status_var).pack(side=tk.LEFT)

        self.readings_tree = ttk.Treeview(
            self.reading_tab,
            columns=("name", "value", "updated", "elapsed"),
            show="headings",
            height=14,
        )
        self.readings_tree.heading("name", text="Variavel")
        self.readings_tree.heading("value", text="Valor")
        self.readings_tree.heading("updated", text="Atualizado em")
        self.readings_tree.heading("elapsed", text="Tempo req.")
        self.readings_tree.column("name", width=340)
        self.readings_tree.column("value", width=220)
        self.readings_tree.column("updated", width=140)
        self.readings_tree.column("elapsed", width=100)
        self.readings_tree.grid(row=1, column=0, sticky=tk.NSEW, pady=8)

        ttk.Label(self.reading_tab, text="Log", style="Section.TLabel").grid(row=2, column=0, sticky=tk.W)
        self.read_log = tk.Text(self.reading_tab, height=9, wrap=tk.WORD)
        self.read_log.grid(row=3, column=0, sticky=tk.EW)

    def _set_status(self, message: str) -> None:
        self.status_var.set(message)
        self.update_idletasks()

    def _set_text(self, widget: tk.Text, content: str) -> None:
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, content)
        widget.configure(state=tk.DISABLED)

    def _append_text(self, widget: tk.Text, content: str) -> None:
        widget.configure(state=tk.NORMAL)
        widget.insert(tk.END, content + "\n")
        widget.configure(state=tk.DISABLED)
        widget.see(tk.END)

    def _run_async(self, label: str, worker, on_success) -> None:
        self._set_status(label)

        def target() -> None:
            try:
                result = worker()
            except Exception as exc:  # noqa: BLE001 - shown to operator
                self.after(0, lambda: self._show_error(str(exc)))
                return
            self.after(0, lambda: on_success(result))

        threading.Thread(target=target, daemon=True).start()

    def _show_error(self, message: str) -> None:
        self._set_status("Erro.")
        messagebox.showerror("BOSS Redfish Wizard", message)

    def _resolve_urls(self) -> BossUrls:
        self.urls = normalize_boss_urls(self.boss_url_var.get())
        return self.urls

    def run_diagnose(self) -> None:
        def worker():
            return diagnose_boss(self.boss_url_var.get())

        def done(report) -> None:
            self.urls = report.urls
            lines = []
            for probe in report.probes:
                status = probe.status if probe.status is not None else "-"
                marker = "OK" if probe.ok else "ERRO"
                lines.append(f"[{marker}] {probe.name:<30} {status:<4} {probe.url}")
                if probe.message:
                    lines.append(f"      {probe.message}")
            self._set_text(self.diagnostic_text, "\n".join(lines))
            self._set_status("Diagnostico concluido.")

        self._run_async("Diagnosticando BOSS...", worker, done)

    def load_catalog(self) -> None:
        def worker():
            urls = self._resolve_urls()
            _status, _content_type, xml_text = fetch_text(urls.acquiredp_url, timeout=20)
            return parse_acquiredp(xml_text)

        def done(catalog: AcquiredpCatalog) -> None:
            self.catalog = catalog
            self.refresh_devices()
            self.notebook.select(self.selection_tab)
            self._set_status(f"{len(catalog.devices)} controladores carregados.")

        self._run_async("Carregando acquiredp...", worker, done)

    def refresh_devices(self) -> None:
        if self.catalog is None:
            return
        self.visible_devices = filter_devices(self.catalog.devices, self.device_filter_var.get())
        self.device_list.delete(0, tk.END)
        for device in self.visible_devices[:100]:
            self.device_list.insert(tk.END, f"{device.code} | {device.name} | {device.type_name}")

    def select_device_from_list(self) -> None:
        selection = self.device_list.curselection()
        if not selection:
            return
        self.current_device = self.visible_devices[selection[0]]
        self.refresh_variables()
        self._set_status(f"Controlador selecionado: {self.current_device.code} - {self.current_device.name}")

    def refresh_variables(self) -> None:
        self.variable_list.delete(0, tk.END)
        self.visible_variables = []
        if self.catalog is None or self.current_device is None:
            return
        all_variables = self.catalog.variables_for_device(self.current_device)
        self.visible_variables = filter_variables(all_variables, self.variable_filter_var.get())
        for variable in self.visible_variables[:250]:
            self.variable_list.insert(tk.END, f"{variable.label} | {variable.code} | {variable.group} | {variable.kind}")

    def add_selected_variables(self) -> None:
        for index in self.variable_list.curselection():
            if index >= len(self.visible_variables):
                continue
            variable = self.visible_variables[index]
            if variable not in self.selected_variables:
                self.selected_variables.append(variable)
        self.refresh_selected_tree()
        self.refresh_template_preview()

    def clear_selected_variables(self) -> None:
        self.selected_variables = []
        self.refresh_selected_tree()
        self.refresh_template_preview()

    def refresh_selected_tree(self) -> None:
        for item in self.selected_tree.get_children():
            self.selected_tree.delete(item)
        for variable in self.selected_variables:
            self.selected_tree.insert("", tk.END, values=(variable.code, variable.group, variable.kind))

    def refresh_template_preview(self) -> None:
        for item in self.preview_tree.get_children():
            self.preview_tree.delete(item)
        if self.current_device is None:
            return
        for row in template_preview_rows(self.current_device, self.selected_variables):
            self.preview_tree.insert(
                "",
                tk.END,
                values=(row["name"], row["variable_code"], row["resource_id"], row["placeholder"]),
            )
        if self.selected_variables:
            self.notebook.select(self.template_tab)

    def choose_output_zip(self) -> None:
        filename = filedialog.asksaveasfilename(
            title="Salvar template Redfish",
            defaultextension=".zip",
            filetypes=[("ZIP", "*.zip")],
            initialfile=Path(self.output_zip_var.get()).name,
        )
        if filename:
            self.output_zip_var.set(filename)

    def generate_template(self) -> None:
        if self.current_device is None:
            self._show_error("Selecione um controlador.")
            return
        if not self.selected_variables:
            self._show_error("Selecione pelo menos uma variavel.")
            return
        output_zip = Path(self.output_zip_var.get())
        self.generated_zip = create_generic_template_archive(
            output_zip=output_zip,
            device=self.current_device,
            variables=self.selected_variables,
            chassis_id=chassis_id_for_device(self.current_device),
        )
        self._set_text(self.import_text, manual_import_steps(self.generated_zip))
        self._set_status(f"Template gerado: {self.generated_zip}")
        messagebox.showinfo("Template gerado", f"Arquivo gerado:\n{self.generated_zip}")

    def show_manual_import(self) -> None:
        path = self.generated_zip or Path(self.output_zip_var.get())
        self._set_text(self.import_text, manual_import_steps(path))
        self.notebook.select(self.template_tab)

    def _redfish_base_url(self) -> str:
        urls = self.urls or self._resolve_urls()
        return urls.redfish_base

    def _selected_sensor_ids(self) -> list[str]:
        if self.current_device is None:
            return []
        return [sensor.resource_id for sensor in build_sensor_definitions(self.current_device.code, self.selected_variables)]

    def _selected_chassis_id(self) -> str:
        if self.current_device is None:
            raise ValueError("nenhum controlador selecionado")
        return chassis_id_for_device(self.current_device)

    def read_selected_values(self) -> None:
        sensor_ids = self._selected_sensor_ids()
        if not sensor_ids:
            self._show_error("Nenhum sensor selecionado para leitura.")
            return
        self._read_values(self._selected_chassis_id(), sensor_ids)

    def _read_values(self, chassis_id: str, sensor_ids: list[str]) -> None:
        password = self.redfish_password_var.get()
        if not password:
            self._show_error("Informe a senha Redfish admin na aba Conexao.")
            return

        def worker():
            client = RedfishClient(
                base_url=self._redfish_base_url(),
                username="admin",
                password=password,
                verify_tls=False,
                timeout=20,
            )
            started = time.monotonic()
            readings = client.read_sensors(chassis_id, sensor_ids)
            elapsed_ms = max(0, round((time.monotonic() - started) * 1000))
            return readings, elapsed_ms

        def done(result) -> None:
            readings, elapsed_ms = result
            self._show_readings(readings, elapsed_ms)
            self._append_text(self.read_log, f"Leitura concluida: {chassis_id} / {', '.join(sensor_ids)} ({elapsed_ms} ms)")
            self._set_status("Leitura concluida.")

        self._run_async("Lendo Redfish...", worker, done)

    def _show_readings(self, readings, elapsed_ms: int, *, select_tab: bool = True) -> None:
        updated_at = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        for item in self.readings_tree.get_children():
            self.readings_tree.delete(item)
        for name, value in reading_table_rows(readings):
            self.readings_tree.insert("", tk.END, values=(name, value, updated_at, f"{elapsed_ms} ms"))
        if select_tab:
            self.notebook.select(self.reading_tab)

    def start_polling(self) -> None:
        sensor_ids = self._selected_sensor_ids()
        if not sensor_ids:
            self._show_error("Nenhum sensor selecionado para polling.")
            return
        password = self.redfish_password_var.get()
        if not password:
            self._show_error("Informe a senha Redfish admin na aba Conexao.")
            return
        try:
            polling_ms = parse_polling_ms(self.polling_ms_var.get())
        except ValueError as exc:
            self._show_error(str(exc))
            return
        if self._polling_active:
            self._set_status("Polling ja esta ativo.")
            return

        chassis_id = self._selected_chassis_id()
        self._polling_client = RedfishClient(
            base_url=self._redfish_base_url(),
            username="admin",
            password=password,
            verify_tls=False,
            timeout=20,
        )
        self._polling_active = True
        self._polling_inflight = False
        self.polling_status_var.set(f"Polling ativo: {polling_ms} ms")
        self._set_status(f"Polling ativo: {polling_ms} ms")
        if polling_is_below_recommended(polling_ms):
            self._append_text(self.read_log, "Aviso: polling abaixo de 500 ms pode aumentar a carga no BOSS.")
        self._append_text(self.read_log, f"Polling iniciado: {chassis_id} / {', '.join(sensor_ids)}")
        self._poll_values(chassis_id, sensor_ids, polling_ms)

    def stop_polling(self) -> None:
        self._polling_active = False
        self._polling_inflight = False
        self._polling_client = None
        if self._polling_after_id is not None:
            self.after_cancel(self._polling_after_id)
            self._polling_after_id = None
        self.polling_status_var.set("Polling parado.")
        self._set_status("Polling parado.")

    def _poll_values(self, chassis_id: str, sensor_ids: list[str], polling_ms: int) -> None:
        if not self._polling_active or self._polling_inflight or self._polling_client is None:
            return
        client = self._polling_client
        self._polling_after_id = None
        self._polling_inflight = True
        self.polling_status_var.set("Polling em andamento...")

        def target() -> None:
            started = time.monotonic()
            try:
                readings = client.read_sensors(chassis_id, sensor_ids)
                elapsed_ms = max(0, round((time.monotonic() - started) * 1000))
            except Exception as exc:  # noqa: BLE001 - shown to operator
                message = str(exc)
                self.after(0, lambda: self._poll_failed(message))
                return
            self.after(0, lambda: self._poll_done(chassis_id, sensor_ids, polling_ms, readings, elapsed_ms))

        threading.Thread(target=target, daemon=True).start()

    def _poll_done(self, chassis_id: str, sensor_ids: list[str], polling_ms: int, readings, elapsed_ms: int) -> None:
        self._polling_inflight = False
        self._show_readings(readings, elapsed_ms, select_tab=False)
        self._append_text(self.read_log, f"Polling OK: {chassis_id} / {', '.join(sensor_ids)} ({elapsed_ms} ms)")
        if not self._polling_active:
            self.polling_status_var.set("Polling parado.")
            return
        self.polling_status_var.set(f"Polling ativo: {polling_ms} ms")
        delay_ms = max(0, polling_ms - elapsed_ms)
        self._polling_after_id = self.after(delay_ms, lambda: self._poll_values(chassis_id, sensor_ids, polling_ms))

    def _poll_failed(self, message: str) -> None:
        self._polling_active = False
        self._polling_inflight = False
        self._polling_client = None
        self.polling_status_var.set("Polling parado por erro.")
        self._show_error(message)


def main() -> int:
    app = RedfishWizardApp()
    app.mainloop()
    return 0
