import calendar
import base64
import json
import os
import subprocess
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import messagebox, ttk


# El archivo de datos se guarda junto a este programa.
ARCHIVO_TAREAS = Path(__file__).parent / "tareas.json"

FILTROS = ("Todas", "Pendientes", "Completadas", "Vencidas")
HORAS = tuple(f"{hora:02d}" for hora in range(24))
MINUTOS = tuple(f"{minuto:02d}" for minuto in range(60))
HORA_PREDETERMINADA = "23:59"
RECORDATORIOS = {
    "Sin recordatorio": None,
    "5 minutos antes": 5,
    "10 minutos antes": 10,
    "15 minutos antes": 15,
    "30 minutos antes": 30,
    "1 hora antes": 60,
    "1 día antes": 1440,
}
RECORDATORIO_OPCIONES = tuple(RECORDATORIOS)
RECORDATORIO_MINUTOS_VALIDOS = set(RECORDATORIOS.values()) - {None}
MESES = (
    "",
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
)

COLORES = {
    "claro": {
        "fondo": "#f3f4f6",
        "panel": "#ffffff",
        "texto": "#1f2937",
        "texto_suave": "#6b7280",
        "subtitulo": "#374151",
        "entrada": "#ffffff",
        "lista": "#ffffff",
        "seleccion": "#2563eb",
        "seleccion_texto": "#ffffff",
        "completada": "#dcfce7",
        "vencida": "#fee2e2",
        "calendario_seleccion": "#2563eb",
    },
    "oscuro": {
        "fondo": "#111827",
        "panel": "#1f2937",
        "texto": "#f9fafb",
        "texto_suave": "#d1d5db",
        "subtitulo": "#f9fafb",
        "entrada": "#374151",
        "lista": "#1f2937",
        "seleccion": "#1d4ed8",
        "seleccion_texto": "#ffffff",
        "completada": "#14532d",
        "vencida": "#7f1d1d",
        "calendario_seleccion": "#2563eb",
    },
}

tareas = []
indices_visibles = []
modo_oscuro = False
fecha_seleccionada = date.today()
mes_calendario = date.today().replace(day=1)
botones_calendario = []


def fecha_valida(fecha_texto):
    """Comprueba una fecha guardada con el formato AAAA-MM-DD."""
    try:
        datetime.strptime(fecha_texto, "%Y-%m-%d")
        return True
    except (TypeError, ValueError):
        return False


def hora_valida(hora_texto):
    """Comprueba una hora guardada con el formato HH:MM."""
    try:
        datetime.strptime(hora_texto, "%H:%M")
        return True
    except (TypeError, ValueError):
        return False


def tarea_normalizada(tarea):
    """Adapta tareas antiguas al formato actual sin perder su texto ni estado."""
    if not isinstance(tarea, dict):
        return None

    fecha_limite = tarea.get("fecha_limite") or date.today().isoformat()
    if not fecha_valida(fecha_limite):
        fecha_limite = date.today().isoformat()

    hora_limite = tarea.get("hora_limite") or HORA_PREDETERMINADA
    if not hora_valida(hora_limite):
        hora_limite = HORA_PREDETERMINADA

    recordatorio = tarea.get("recordatorio")
    if isinstance(recordatorio, str):
        recordatorio = RECORDATORIOS.get(recordatorio)
    else:
        try:
            recordatorio = int(recordatorio) if recordatorio is not None else None
        except (TypeError, ValueError):
            recordatorio = None

    if recordatorio not in RECORDATORIO_MINUTOS_VALIDOS:
        recordatorio = None

    return {
        "texto": str(tarea.get("texto", "")).strip(),
        "completada": bool(tarea.get("completada", False)),
        "fecha_limite": fecha_limite,
        "hora_limite": hora_limite,
        "fijada": bool(tarea.get("fijada", False)),
        "recordatorio": recordatorio,
        "recordatorio_mostrado": bool(tarea.get("recordatorio_mostrado", False)),
    }


def cargar_tareas():
    """Carga tareas.json y adapta los datos al formato actual."""
    global tareas

    if not ARCHIVO_TAREAS.exists():
        tareas = []
        return

    try:
        with ARCHIVO_TAREAS.open("r", encoding="utf-8") as archivo:
            datos = json.load(archivo)

        tareas = []
        if isinstance(datos, list):
            for dato in datos:
                tarea = tarea_normalizada(dato)
                if tarea is not None and tarea["texto"]:
                    tareas.append(tarea)
    except (json.JSONDecodeError, OSError):
        tareas = []


def guardar_tareas():
    """Guarda únicamente los campos actuales de cada tarea."""
    try:
        with ARCHIVO_TAREAS.open("w", encoding="utf-8") as archivo:
            json.dump(tareas, archivo, ensure_ascii=False, indent=4)
    except OSError:
        messagebox.showerror("Error", "No se pudieron guardar las tareas.")


def tarea_vencida(tarea):
    """Una tarea pendiente vence al pasar su fecha y hora límite."""
    if tarea["completada"]:
        return False

    try:
        limite = datetime.strptime(
            f"{tarea['fecha_limite']} {tarea['hora_limite']}",
            "%Y-%m-%d %H:%M",
        )
        return datetime.now() > limite
    except (KeyError, TypeError, ValueError):
        return False


def nombre_recordatorio(minutos):
    """Devuelve el texto visible de una opción de recordatorio."""
    for nombre, valor in RECORDATORIOS.items():
        if valor == minutos:
            return nombre
    return "Sin recordatorio"


def texto_del_recordatorio(minutos):
    if minutos == 60:
        return "Falta 1 hora para la hora programada."
    if minutos == 1440:
        return "Falta 1 día para la hora programada."
    return f"Faltan {minutos} minutos para la hora programada."


def mostrar_notificacion_windows(tarea):
    """Muestra una notificación Toast de Windows sin reproducir sonido."""
    titulo = "⏰ Recordatorio"
    mensaje = (
        f"{tarea['texto']}\n"
        f"{texto_del_recordatorio(tarea['recordatorio'])}"
    )

    if os.name != "nt":
        messagebox.showinfo(titulo, mensaje)
        return

    # Se escapan las comillas simples antes de incluir texto del usuario
    # dentro del script de PowerShell.
    titulo_ps = titulo.replace("'", "''")
    mensaje_ps = mensaje.replace("'", "''")
    script = f"""
$Titulo = '{titulo_ps}'
$Mensaje = '{mensaje_ps}'
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType=WindowsRuntime] | Out-Null
[Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
$Xml = [Windows.Data.Xml.Dom.XmlDocument]::new()
$Xml.LoadXml('<toast><visual><binding template="ToastGeneric"><text></text><text></text></binding></visual><audio silent="true"/></toast>')
$TextNodes = $Xml.GetElementsByTagName('text')
$TextNodes.Item(0).AppendChild($Xml.CreateTextNode($Titulo)) | Out-Null
$TextNodes.Item(1).AppendChild($Xml.CreateTextNode($Mensaje)) | Out-Null
$Toast = [Windows.UI.Notifications.ToastNotification]::new($Xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('ListaTareas').Show($Toast)
"""
    comando_codificado = base64.b64encode(
        script.encode("utf-16le")
    ).decode("ascii")

    try:
        resultado = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-WindowStyle",
                "Hidden",
                "-EncodedCommand",
                comando_codificado,
            ],
            capture_output=True,
            timeout=5,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if resultado.returncode != 0:
            raise OSError("PowerShell no pudo crear la notificación Toast.")
    except (OSError, subprocess.SubprocessError):
        # Fallback para equipos donde las Toast de escritorio estén desactivadas.
        messagebox.showinfo(titulo, mensaje)


def revisar_recordatorios():
    """Busca recordatorios pendientes mientras la ventana está abierta."""
    ahora = datetime.now()
    hubo_cambios = False

    for tarea in tareas:
        minutos = tarea.get("recordatorio")
        if (
            tarea.get("completada")
            or minutos is None
            or tarea.get("recordatorio_mostrado", False)
        ):
            continue

        try:
            programada = datetime.strptime(
                f"{tarea['fecha_limite']} {tarea['hora_limite']}",
                "%Y-%m-%d %H:%M",
            )
            momento_recordatorio = programada - timedelta(minutes=minutos)
        except (KeyError, TypeError, ValueError):
            continue

        if momento_recordatorio <= ahora < programada:
            mostrar_notificacion_windows(tarea)
            tarea["recordatorio_mostrado"] = True
            hubo_cambios = True

    if hubo_cambios:
        guardar_tareas()

    ventana.after(15000, revisar_recordatorios)


def tarea_coincide(tarea):
    """Aplica la búsqueda y el filtro elegidos por el usuario."""
    busqueda = buscar_var.get().strip().lower()
    texto_completo = (
        f"{tarea['texto']} {tarea['fecha_limite']} {tarea['hora_limite']}"
    ).lower()

    if busqueda and busqueda not in texto_completo:
        return False

    filtro = filtro_var.get()
    if filtro == "Pendientes" and tarea["completada"]:
        return False
    if filtro == "Completadas" and not tarea["completada"]:
        return False
    if filtro == "Vencidas" and not tarea_vencida(tarea):
        return False

    return True


def actualizar_estadisticas():
    total = len(tareas)
    completadas = sum(1 for tarea in tareas if tarea["completada"])
    pendientes = total - completadas
    vencidas = sum(1 for tarea in tareas if tarea_vencida(tarea))
    estadisticas_var.set(
        f"Total: {total}    |    Pendientes: {pendientes}    |    "
        f"Completadas: {completadas}    |    Vencidas: {vencidas}"
    )


def mostrar_tareas():
    """Redibuja la lista, colocando las tareas fijadas en la parte superior."""
    global indices_visibles

    colores = COLORES["oscuro" if modo_oscuro else "claro"]
    lista_tareas.delete(0, tk.END)
    indices_visibles = []

    # La función sorted mantiene el orden original entre tareas fijadas.
    tareas_ordenadas = sorted(
        enumerate(tareas),
        key=lambda elemento: (not elemento[1]["fijada"], elemento[0]),
    )

    for indice, tarea in tareas_ordenadas:
        if not tarea_coincide(tarea):
            continue

        estado = "✓" if tarea["completada"] else "□"
        fijada = "📌 " if tarea["fijada"] else ""
        texto = (
            f"{fijada}{estado} {tarea['texto']}   |   "
            f"Límite: {tarea['fecha_limite']} {tarea['hora_limite']}"
        )
        if tarea["recordatorio"] is not None:
            texto += f"   |   Aviso: {nombre_recordatorio(tarea['recordatorio'])}"
        if tarea_vencida(tarea):
            texto += "   |   ⚠ VENCIDA"

        lista_tareas.insert(tk.END, texto)
        indice_visual = lista_tareas.size() - 1
        indices_visibles.append(indice)

        if tarea_vencida(tarea):
            fondo = colores["vencida"]
            texto_color = "#fecaca" if modo_oscuro else "#991b1b"
        elif tarea["completada"]:
            fondo = colores["completada"]
            texto_color = colores["texto_suave"]
        else:
            fondo = colores["lista"]
            texto_color = colores["texto"]

        lista_tareas.itemconfig(
            indice_visual,
            foreground=texto_color,
            background=fondo,
        )

    actualizar_estadisticas()


def obtener_indice_seleccionado(mostrar_aviso=True):
    seleccion = lista_tareas.curselection()
    if not seleccion:
        if mostrar_aviso:
            messagebox.showwarning("Sin selección", "Selecciona una tarea primero.")
        return None

    indice_visual = seleccion[0]
    if indice_visual >= len(indices_visibles):
        return None
    return indices_visibles[indice_visual]


def seleccionar_fecha(dia):
    global fecha_seleccionada
    fecha_seleccionada = date(mes_calendario.year, mes_calendario.month, dia)
    actualizar_calendario()


def cambiar_mes(cantidad):
    global mes_calendario

    nuevo_mes = mes_calendario.month + cantidad
    nuevo_anio = mes_calendario.year
    if nuevo_mes < 1:
        nuevo_mes = 12
        nuevo_anio -= 1
    elif nuevo_mes > 12:
        nuevo_mes = 1
        nuevo_anio += 1

    mes_calendario = date(nuevo_anio, nuevo_mes, 1)
    actualizar_calendario()


def actualizar_calendario():
    """Dibuja un calendario mensual usando únicamente widgets de Tkinter."""
    colores = COLORES["oscuro" if modo_oscuro else "claro"]

    etiqueta_mes.configure(
        text=f"{MESES[mes_calendario.month]} "
        f"{mes_calendario.year}",
        background=colores["fondo"],
        foreground=colores["texto"],
    )
    etiqueta_fecha_seleccionada.configure(
        text=f"Fecha elegida: {fecha_seleccionada.strftime('%d/%m/%Y')}",
        background=colores["fondo"],
        foreground=colores["texto_suave"],
    )

    for widget in marco_dias.winfo_children():
        widget.destroy()
    botones_calendario.clear()

    nombres_dias = ("L", "M", "X", "J", "V", "S", "D")
    for columna, nombre in enumerate(nombres_dias):
        tk.Label(
            marco_dias,
            text=nombre,
            width=4,
            background=colores["fondo"],
            foreground=colores["texto_suave"],
            font=("Segoe UI", 9, "bold"),
        ).grid(row=0, column=columna, padx=1, pady=(2, 4))

    primer_dia, cantidad_dias = calendar.monthrange(
        mes_calendario.year,
        mes_calendario.month,
    )
    for dia in range(1, cantidad_dias + 1):
        posicion = primer_dia + dia - 1
        fila = posicion // 7 + 1
        columna = posicion % 7
        fecha_del_boton = date(mes_calendario.year, mes_calendario.month, dia)
        es_seleccionada = fecha_del_boton == fecha_seleccionada

        boton = tk.Button(
            marco_dias,
            text=str(dia),
            width=4,
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            command=lambda dia_actual=dia: seleccionar_fecha(dia_actual),
            background=(
                colores["calendario_seleccion"]
                if es_seleccionada
                else colores["panel"]
            ),
            foreground="#ffffff" if es_seleccionada else colores["texto"],
            activebackground=colores["seleccion"],
            activeforeground="#ffffff",
        )
        boton.grid(row=fila, column=columna, padx=1, pady=1, ipady=3)
        botones_calendario.append(boton)


def preparar_fecha_y_hora(fecha_texto, hora_texto):
    """Selecciona en el formulario una fecha y hora guardadas."""
    global fecha_seleccionada, mes_calendario

    try:
        fecha_seleccionada = datetime.strptime(fecha_texto, "%Y-%m-%d").date()
    except ValueError:
        fecha_seleccionada = date.today()

    mes_calendario = fecha_seleccionada.replace(day=1)
    partes = hora_texto.split(":")
    hora_var.set(partes[0])
    minuto_var.set(partes[1])
    actualizar_calendario()


def limpiar_formulario():
    global fecha_seleccionada, mes_calendario

    entrada_tarea.delete(0, tk.END)
    fecha_seleccionada = date.today()
    mes_calendario = fecha_seleccionada.replace(day=1)
    hora_var.set("20")
    minuto_var.set("00")
    recordatorio_var.set("Sin recordatorio")
    actualizar_calendario()
    entrada_tarea.focus()


def agregar_tarea():
    texto = entrada_tarea.get().strip()
    if not texto:
        messagebox.showwarning("Tarea vacía", "Escribe una tarea antes de agregarla.")
        return

    tareas.append(
        {
            "texto": texto,
            "completada": False,
            "fecha_limite": fecha_seleccionada.isoformat(),
            "hora_limite": f"{hora_var.get()}:{minuto_var.get()}",
            "fijada": False,
            "recordatorio": RECORDATORIOS[recordatorio_var.get()],
            "recordatorio_mostrado": False,
        }
    )
    guardar_tareas()
    limpiar_formulario()
    mostrar_tareas()
    messagebox.showinfo("Tarea agregada", "La tarea se agregó correctamente.")


def cargar_seleccion_en_formulario(event=None):
    indice = obtener_indice_seleccionado(mostrar_aviso=False)
    if indice is None:
        return

    tarea = tareas[indice]
    entrada_tarea.delete(0, tk.END)
    entrada_tarea.insert(0, tarea["texto"])
    preparar_fecha_y_hora(tarea["fecha_limite"], tarea["hora_limite"])
    recordatorio_var.set(nombre_recordatorio(tarea["recordatorio"]))


def editar_tarea():
    indice = obtener_indice_seleccionado()
    if indice is None:
        return

    texto = entrada_tarea.get().strip()
    if not texto:
        messagebox.showwarning("Tarea vacía", "Escribe una tarea antes de continuar.")
        return

    tareas[indice]["texto"] = texto
    tareas[indice]["fecha_limite"] = fecha_seleccionada.isoformat()
    tareas[indice]["hora_limite"] = f"{hora_var.get()}:{minuto_var.get()}"
    tareas[indice]["recordatorio"] = RECORDATORIOS[recordatorio_var.get()]
    tareas[indice]["recordatorio_mostrado"] = False
    guardar_tareas()
    limpiar_formulario()
    mostrar_tareas()
    messagebox.showinfo("Tarea editada", "La tarea se actualizó correctamente.")


def completar_tarea():
    indice = obtener_indice_seleccionado()
    if indice is None:
        return

    tareas[indice]["completada"] = True
    guardar_tareas()
    mostrar_tareas()
    messagebox.showinfo("Tarea completada", "La tarea se marcó como completada.")


def fijar_tarea():
    indice = obtener_indice_seleccionado()
    if indice is None:
        return

    tareas[indice]["fijada"] = not tareas[indice]["fijada"]
    estado = "fijada" if tareas[indice]["fijada"] else "desfijada"
    guardar_tareas()
    mostrar_tareas()
    messagebox.showinfo("Tarea actualizada", f"La tarea quedó {estado}.")


def eliminar_tarea():
    indice = obtener_indice_seleccionado()
    if indice is None:
        return

    confirmacion = messagebox.askyesno(
        "Confirmar eliminación",
        f"¿Seguro que deseas eliminar la tarea?\n\n{tareas[indice]['texto']}",
    )
    if not confirmacion:
        return

    tareas.pop(indice)
    guardar_tareas()
    limpiar_formulario()
    mostrar_tareas()
    messagebox.showinfo("Tarea eliminada", "La tarea se eliminó correctamente.")


def aplicar_colores():
    """Aplica el modo claro u oscuro a los controles principales."""
    colores = COLORES["oscuro" if modo_oscuro else "claro"]
    ventana.configure(background=colores["fondo"])

    for marco in marcos:
        marco.configure(background=colores["fondo"])
    for etiqueta in etiquetas:
        etiqueta.configure(
            background=colores["fondo"],
            foreground=colores["texto"],
        )
    subtitulo.configure(
        background=colores["fondo"],
        foreground=colores["subtitulo"],
    )
    etiqueta_estadisticas.configure(foreground=colores["texto_suave"])

    for entrada in entradas:
        entrada.configure(
            background=colores["entrada"],
            foreground=colores["texto"],
            insertbackground=colores["texto"],
        )

    lista_tareas.configure(
        background=colores["lista"],
        foreground=colores["texto"],
        selectbackground=colores["seleccion"],
        selectforeground=colores["seleccion_texto"],
    )
    boton_modo.configure(
        text="☀ Modo claro" if modo_oscuro else "☾ Modo oscuro",
        background="#374151" if modo_oscuro else "#e5e7eb",
        foreground="#ffffff" if modo_oscuro else "#1f2937",
    )
    estilo.configure(
        "App.TCombobox",
        fieldbackground=colores["entrada"],
        background=colores["panel"],
        foreground=colores["texto"],
        arrowcolor=colores["texto"],
        selectbackground=colores["seleccion"],
        selectforeground=colores["seleccion_texto"],
    )
    estilo.map(
        "App.TCombobox",
        fieldbackground=[
            ("readonly", colores["entrada"]),
            ("focus", colores["entrada"]),
        ],
        foreground=[
            ("readonly", colores["texto"]),
            ("focus", colores["texto"]),
        ],
        selectbackground=[
            ("readonly", colores["seleccion"]),
            ("focus", colores["seleccion"]),
        ],
        selectforeground=[
            ("readonly", colores["seleccion_texto"]),
            ("focus", colores["seleccion_texto"]),
        ],
    )
    # La lista desplegable interna de ttk.Combobox también necesita contraste.
    ventana.option_add(
        "*TCombobox*Listbox.selectBackground",
        colores["seleccion"],
    )
    ventana.option_add(
        "*TCombobox*Listbox.selectForeground",
        colores["seleccion_texto"],
    )
    actualizar_calendario()
    mostrar_tareas()


def cambiar_modo():
    global modo_oscuro
    modo_oscuro = not modo_oscuro
    aplicar_colores()


def cerrar_aplicacion():
    guardar_tareas()
    ventana.destroy()


# Ventana principal.
ventana = tk.Tk()
ventana.title("Gestor de tareas")
ventana.geometry("1050x760")
ventana.minsize(800, 620)

estilo = ttk.Style(ventana)
try:
    estilo.theme_use("clam")
except tk.TclError:
    pass

fuente_normal = ("Segoe UI", 10)
fuente_pequena = ("Segoe UI", 9)
fuente_titulo = ("Segoe UI", 23, "bold")

marco_principal = tk.Frame(ventana, padx=28, pady=24)
marco_principal.pack(fill="both", expand=True)

marco_encabezado = tk.Frame(marco_principal)
marco_encabezado.pack(fill="x")

titulo = tk.Label(marco_encabezado, text="Mis tareas", font=fuente_titulo)
titulo.pack(side="left")

subtitulo = tk.Label(
    marco_encabezado,
    text="Organiza tus pendientes con fecha y hora",
    font=("Segoe UI", 12, "bold"),
)
subtitulo.pack(side="left", padx=(14, 0), pady=(11, 0))

boton_modo = tk.Button(
    marco_encabezado,
    text="☾ Modo oscuro",
    command=cambiar_modo,
    relief="flat",
    padx=12,
    pady=6,
    cursor="hand2",
)
boton_modo.pack(side="right")

marco_busqueda = tk.Frame(marco_principal, pady=18)
marco_busqueda.pack(fill="x")

etiqueta_busqueda = tk.Label(marco_busqueda, text="Buscar:", font=fuente_normal)
etiqueta_busqueda.pack(side="left")

buscar_var = tk.StringVar()
entrada_busqueda = tk.Entry(marco_busqueda, textvariable=buscar_var, font=fuente_normal)
entrada_busqueda.pack(side="left", fill="x", expand=True, padx=(8, 18), ipady=6)

etiqueta_filtro = tk.Label(marco_busqueda, text="Mostrar:", font=fuente_normal)
etiqueta_filtro.pack(side="left")

filtro_var = tk.StringVar(value="Todas")
filtro_menu = ttk.Combobox(
    marco_busqueda,
    textvariable=filtro_var,
    values=FILTROS,
    state="readonly",
    width=15,
    style="App.TCombobox",
)
filtro_menu.pack(side="left", padx=(8, 0))

marco_formulario = tk.Frame(marco_principal, pady=4)
marco_formulario.pack(fill="x")

etiqueta_texto = tk.Label(marco_formulario, text="Tarea", font=fuente_pequena)
etiqueta_texto.grid(row=0, column=0, columnspan=4, sticky="w")
entrada_tarea = tk.Entry(marco_formulario, font=fuente_normal)
entrada_tarea.grid(row=1, column=0, columnspan=4, sticky="ew", ipady=6)

marco_fecha = tk.Frame(marco_formulario, pady=12)
marco_fecha.grid(row=2, column=0, columnspan=3, sticky="w")

etiqueta_fecha = tk.Label(marco_fecha, text="Fecha límite", font=fuente_pequena)
etiqueta_fecha.pack(anchor="w")

marco_calendario = tk.Frame(marco_fecha)
marco_calendario.pack(anchor="w", pady=(4, 0))

marco_navegacion = tk.Frame(marco_calendario)
marco_navegacion.pack(fill="x")

boton_mes_anterior = tk.Button(
    marco_navegacion,
    text="‹",
    command=lambda: cambiar_mes(-1),
    relief="flat",
    width=3,
    cursor="hand2",
)
boton_mes_anterior.pack(side="left")

etiqueta_mes = tk.Label(marco_navegacion, font=("Segoe UI", 10, "bold"), width=18)
etiqueta_mes.pack(side="left", padx=4)

boton_mes_siguiente = tk.Button(
    marco_navegacion,
    text="›",
    command=lambda: cambiar_mes(1),
    relief="flat",
    width=3,
    cursor="hand2",
)
boton_mes_siguiente.pack(side="left")

marco_dias = tk.Frame(marco_calendario)
marco_dias.pack()

etiqueta_fecha_seleccionada = tk.Label(marco_fecha, font=fuente_pequena)
etiqueta_fecha_seleccionada.pack(anchor="w", pady=(5, 0))

marco_hora = tk.Frame(marco_formulario, pady=12)
marco_hora.grid(row=2, column=3, sticky="n", padx=(26, 0))

etiqueta_hora = tk.Label(marco_hora, text="Hora límite", font=fuente_pequena)
etiqueta_hora.pack(anchor="w")

marco_selectores_hora = tk.Frame(marco_hora)
marco_selectores_hora.pack(anchor="w", pady=(15, 0))

hora_var = tk.StringVar(value="20")
hora_menu = ttk.Combobox(
    marco_selectores_hora,
    textvariable=hora_var,
    values=HORAS,
    state="readonly",
    width=4,
    style="App.TCombobox",
)
hora_menu.pack(side="left")

etiqueta_dos_puntos = tk.Label(
    marco_selectores_hora,
    text=":",
    font=("Segoe UI", 14, "bold"),
)
etiqueta_dos_puntos.pack(
    side="left", padx=4
)

minuto_var = tk.StringVar(value="00")
minuto_menu = ttk.Combobox(
    marco_selectores_hora,
    textvariable=minuto_var,
    values=MINUTOS,
    state="readonly",
    width=4,
    style="App.TCombobox",
)
minuto_menu.pack(side="left")

etiqueta_ayuda_hora = tk.Label(
    marco_hora,
    text="Selecciona horas y minutos",
    font=fuente_pequena,
)
etiqueta_ayuda_hora.pack(anchor="w", pady=(8, 0))

etiqueta_recordatorio = tk.Label(
    marco_hora,
    text="Recordatorio",
    font=fuente_pequena,
)
etiqueta_recordatorio.pack(anchor="w", pady=(14, 0))

recordatorio_var = tk.StringVar(value="Sin recordatorio")
recordatorio_menu = ttk.Combobox(
    marco_hora,
    textvariable=recordatorio_var,
    values=RECORDATORIO_OPCIONES,
    state="readonly",
    width=21,
    style="App.TCombobox",
)
recordatorio_menu.pack(anchor="w", pady=(4, 0))

for columna in range(4):
    marco_formulario.columnconfigure(columna, weight=1)

entrada_tarea.bind("<Return>", lambda evento: agregar_tarea())

marco_botones = tk.Frame(marco_principal, pady=12)
marco_botones.pack(fill="x")

boton_agregar = tk.Button(
    marco_botones,
    text="＋ Agregar",
    command=agregar_tarea,
    background="#2563eb",
    foreground="white",
    relief="flat",
    padx=12,
    pady=7,
    cursor="hand2",
)
boton_agregar.pack(side="left", padx=(0, 7))

boton_editar = tk.Button(
    marco_botones,
    text="✎ Editar selección",
    command=editar_tarea,
    background="#7c3aed",
    foreground="white",
    relief="flat",
    padx=12,
    pady=7,
    cursor="hand2",
)
boton_editar.pack(side="left", padx=7)

boton_completar = tk.Button(
    marco_botones,
    text="✓ Completar",
    command=completar_tarea,
    background="#16a34a",
    foreground="white",
    relief="flat",
    padx=12,
    pady=7,
    cursor="hand2",
)
boton_completar.pack(side="left", padx=7)

boton_fijar = tk.Button(
    marco_botones,
    text="📌 Fijar / desfijar",
    command=fijar_tarea,
    background="#d97706",
    foreground="white",
    relief="flat",
    padx=12,
    pady=7,
    cursor="hand2",
)
boton_fijar.pack(side="left", padx=7)

boton_eliminar = tk.Button(
    marco_botones,
    text="⌫ Eliminar",
    command=eliminar_tarea,
    background="#dc2626",
    foreground="white",
    relief="flat",
    padx=12,
    pady=7,
    cursor="hand2",
)
boton_eliminar.pack(side="left", padx=7)

marco_lista = tk.Frame(marco_principal)
marco_lista.pack(fill="both", expand=True)

lista_tareas = tk.Listbox(
    marco_lista,
    font=("Segoe UI", 11),
    selectmode=tk.SINGLE,
    exportselection=False,
    activestyle="none",
    borderwidth=0,
    highlightthickness=1,
    relief="flat",
    selectborderwidth=0,
)
lista_tareas.pack(side="left", fill="both", expand=True)

barra_desplazamiento = tk.Scrollbar(marco_lista, command=lista_tareas.yview)
barra_desplazamiento.pack(side="right", fill="y")
lista_tareas.configure(yscrollcommand=barra_desplazamiento.set)
lista_tareas.bind("<<ListboxSelect>>", cargar_seleccion_en_formulario)

marco_estadisticas = tk.Frame(marco_principal, pady=12)
marco_estadisticas.pack(fill="x")
estadisticas_var = tk.StringVar()
etiqueta_estadisticas = tk.Label(
    marco_estadisticas,
    textvariable=estadisticas_var,
    font=("Segoe UI", 10, "bold"),
)
etiqueta_estadisticas.pack(anchor="w")

marcos = [
    marco_principal,
    marco_encabezado,
    marco_busqueda,
    marco_formulario,
    marco_fecha,
    marco_hora,
    marco_calendario,
    marco_navegacion,
    marco_dias,
    marco_selectores_hora,
    marco_botones,
    marco_lista,
    marco_estadisticas,
]
etiquetas = [
    titulo,
    etiqueta_busqueda,
    etiqueta_filtro,
    etiqueta_texto,
    etiqueta_fecha,
    etiqueta_hora,
    etiqueta_fecha_seleccionada,
    etiqueta_dos_puntos,
    etiqueta_ayuda_hora,
    etiqueta_recordatorio,
]
entradas = [entrada_busqueda, entrada_tarea]

buscar_var.trace_add("write", lambda *args: mostrar_tareas())
filtro_var.trace_add("write", lambda *args: mostrar_tareas())

ventana.protocol("WM_DELETE_WINDOW", cerrar_aplicacion)
cargar_tareas()
aplicar_colores()
mostrar_tareas()
entrada_tarea.focus()
ventana.after(1000, revisar_recordatorios)
ventana.mainloop()
