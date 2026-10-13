import sqlite3
import smtplib
import threading
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder

from kivymd.app import MDApp
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.list import MDList, TwoLineListItem
from kivymd.uix.menu import MDDropdownMenu

# ==============================================================================
# CONFIGURACIÓN DE CORREO ELECTRÓNICO PARA INFORMES
# ==============================================================================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
CORREO_EMISOR = "tu_correo@gmail.com"
CORREO_PASSWORD = "tu_clave_de_aplicacion"
CORREO_DESTINATARIO = "destinatario_informe@empresa.cl"

KV = """
MDScreen:
    md_bg_color: 0.93, 0.95, 0.98, 1

    MDBoxLayout:
        orientation: 'vertical'

        # Barra Superior de Navegación
        MDTopAppBar:
            title: "🔒 Control de Casilleros y Candados"
            elevation: 4
            right_action_items:
                [["table", lambda x: app.mostrar_ocupados()], ["email-send", lambda x: app.enviar_informe_manual()]]

        MDScrollView:
            MDBoxLayout:
                orientation: 'vertical'
                padding: "16dp"
                spacing: "16dp"
                size_hint_y: None
                height: self.minimum_height

                # Tarjeta de Indicadores / Estadísticas
                MDCard:
                    orientation: 'horizontal'
                    padding: "12dp"
                    spacing: "12dp"
                    size_hint_y: None
                    height: "60dp"
                    radius: [12,]
                    md_bg_color: 1, 1, 1, 1
                    elevation: 2

                    MDLabel:
                        id: lbl_disp
                        text: "Disponibles: --"
                        bold: True
                        theme_text_color: "Custom"
                        text_color: 0.15, 0.68, 0.37, 1
                        halign: "center"

                    MDLabel:
                        id: lbl_prest
                        text: "Prestados: --"
                        bold: True
                        theme_text_color: "Custom"
                        text_color: 0.9, 0.29, 0.23, 1
                        halign: "center"

                    MDLabel:
                        id: lbl_mov
                        text: "Movimientos Hoy: --"
                        bold: True
                        theme_text_color: "Custom"
                        text_color: 0.16, 0.5, 0.73, 1
                        halign: "center"

                # Selector de Modo: Solicitar vs Devolver
                MDCard:
                    orientation: 'vertical'
                    padding: "16dp"
                    spacing: "10dp"
                    size_hint_y: None
                    height: "110dp"
                    radius: [12,]
                    elevation: 2

                    MDLabel:
                        text: "Seleccione Operación:"
                        font_style: "Subtitle1"
                        bold: True

                    MDBoxLayout:
                        spacing: "12dp"

                        MDRaisedButton:
                            id: btn_solicitar
                            text: "🔑 SOLICITAR CANDADO"
                            size_hint_x: 0.5
                            md_bg_color: 0.15, 0.68, 0.37, 1
                            on_release: app.set_modo("SOLICITAR")

                        MDRaisedButton:
                            id: btn_devolver
                            text: "🔄 DEVOLVER CANDADO"
                            size_hint_x: 0.5
                            md_bg_color: 0.6, 0.6, 0.6, 1
                            on_release: app.set_modo("DEVOLVER")

                # Campo de Lectura / Escaneo de RUT
                MDCard:
                    orientation: 'vertical'
                    padding: "16dp"
                    spacing: "10dp"
                    size_hint_y: None
                    height: "110dp"
                    radius: [12,]
                    elevation: 2

                    MDTextField:
                        id: txt_rut
                        hint_text: "Escanee el carnet o ingrese RUT / Nombre..."
                        font_size: "20sp"
                        on_text_validate: app.procesar_escaneo(self.text)

                # Panel de Resultado de la Operación
                MDCard:
                    id: card_resultado
                    orientation: 'vertical'
                    padding: "20dp"
                    spacing: "10dp"
                    size_hint_y: None
                    height: "260dp"
                    radius: [12,]
                    md_bg_color: 1, 1, 1, 1
                    elevation: 2

                    MDLabel:
                        id: lbl_res_titulo
                        text: "ESPERANDO LECTURA"
                        font_style: "H6"
                        bold: True
                        theme_text_color: "Custom"
                        text_color: 0.5, 0.5, 0.5, 1

                    MDSeparator:

                    MDLabel:
                        id: lbl_res_detalle
                        text: "Seleccione la operación en los botones superiores y pase el carnet por el lector USB/Bluetooth..."
                        font_style: "Body1"
"""


class CasillerosApp(MDApp):

  def __init__(self, **kwargs):
    super().__init__(**kwargs)
    self.modo_actual = "SOLICITAR"
    self.dialog_registro = None
    self.dialog_ocupados = None

  def build(self):
    self.theme_cls.primary_palette = "Blue"
    self.init_db_schema()
    screen = Builder.load_string(KV)
    Clock.schedule_once(lambda dt: self.actualizar_estadisticas(), 0.5)
    return screen

  def init_db_schema(self):
    """Verifica la base de datos e inicializa tablas necesarias."""
    with sqlite3.connect("casilleros.db") as conn:
      cursor = conn.cursor()
      try:
        cursor.execute(
            "ALTER TABLE alumnos ADD COLUMN rol TEXT DEFAULT 'ESTUDIANTE'"
        )
      except sqlite3.OperationalError:
        pass

      cursor.execute("""
                CREATE TABLE IF NOT EXISTS solicitudes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rut TEXT,
                    nombre TEXT,
                    rol TEXT,
                    carrera TEXT,
                    accion TEXT,
                    id_candado TEXT,
                    num_casillero TEXT,
                    fecha_hora DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
      conn.commit()

  def set_modo(self, modo):
    self.modo_actual = modo
    if modo == "SOLICITAR":
      self.root.ids.btn_solicitar.md_bg_color = [0.15, 0.68, 0.37, 1]
      self.root.ids.btn_devolver.md_bg_color = [0.6, 0.6, 0.6, 1]
    else:
      self.root.ids.btn_solicitar.md_bg_color = [0.6, 0.6, 0.6, 1]
      self.root.ids.btn_devolver.md_bg_color = [0.16, 0.5, 0.73, 1]
    self.root.ids.txt_rut.focus = True

  def actualizar_estadisticas(self):
    with sqlite3.connect("casilleros.db") as conn:
      cursor = conn.cursor()
      cursor.execute(
          "SELECT COUNT(*) FROM candados WHERE estado = 'disponible'"
      )
      disp = cursor.fetchone()[0]
      cursor.execute("SELECT COUNT(*) FROM candados WHERE estado = 'prestado'")
      prest = cursor.fetchone()[0]
      cursor.execute(
          "SELECT COUNT(*) FROM solicitudes WHERE DATE(fecha_hora) ="
          " DATE('now', 'localtime')"
      )
      mov_hoy = cursor.fetchone()[0]

    self.root.ids.lbl_disp.text = f"Disponibles: {disp}"
    self.root.ids.lbl_prest.text = f"Prestados: {prest}"
    self.root.ids.lbl_mov.text = f"Movimientos Hoy: {mov_hoy}"

  def procesar_escaneo(self, texto_ingresado):
    rut_busqueda = texto_ingresado.strip()
    self.root.ids.txt_rut.text = ""

    if not rut_busqueda:
      return

    with sqlite3.connect("casilleros.db") as conn:
      cursor = conn.cursor()
      cursor.execute(
          """
                SELECT rut, nombre, carrera, area, COALESCE(rol, 'ESTUDIANTE')
                FROM alumnos
                WHERE rut = ? OR nombre LIKE ?
                LIMIT 1
            """,
          (rut_busqueda, f"%{rut_busqueda}%"),
      )
      alumno = cursor.fetchone()

      if not alumno:
        self.mostrar_modal_registro(rut_busqueda)
        return

      rut, nombre, carrera, area, rol = alumno

      cursor.execute(
          """
                SELECT p.id, p.id_candado, c.num_casillero
                FROM prestamos p
                JOIN candados c ON p.id_candado = c.id_candado
                WHERE p.rut_alumno = ? AND p.estado = 'activo'
            """,
          (rut,),
      )
      prestamo_activo = cursor.fetchone()

      if self.modo_actual == "DEVOLVER":
        if not prestamo_activo:
          self.mostrar_resultado(
              "⚠️ SIN PRÉSTAMOS ACTIVOS",
              f"El usuario {nombre} [{rol}] no registra ningún candado prestado.",
              [0.9, 0.29, 0.23, 1],
          )
          return

        p_id, c_id, cas_num = prestamo_activo
        cursor.execute(
            "UPDATE prestamos SET fecha_devolucion = CURRENT_TIMESTAMP, estado"
            " = 'finalizado' WHERE id = ?",
            (p_id,),
        )
        cursor.execute(
            "UPDATE candados SET estado = 'disponible' WHERE id_candado = ?",
            (c_id,),
        )
        cursor.execute(
            """
                    INSERT INTO solicitudes (rut, nombre, rol, carrera, accion, id_candado, num_casillero)
                    VALUES (?, ?, ?, ?, 'DEVOLUCIÓN', ?, ?)
                """,
            (rut, nombre, rol, carrera, c_id, cas_num),
        )
        conn.commit()

        self.mostrar_resultado(
            "🔄 DEVOLUCIÓN REGISTRADA",
            f"👤 Usuario: {nombre} [{rol}]\n🎓 Carrera: {carrera}\n\n🔑 CANDADO"
            f" LIBERADO: {c_id} (Casillero: {cas_num})",
            [0.16, 0.5, 0.73, 1],
        )

      else:  # Modo SOLICITAR
        if prestamo_activo:
          _, c_id, cas_num = prestamo_activo
          self.mostrar_resultado(
              "⚠️ YA TIENE UN CANDADO ASIGNADO",
              f"El usuario {nombre} [{rol}] ya posee el candado {c_id} (Casillero"
              " {cas_num}).",
              [0.9, 0.29, 0.23, 1],
          )
          return

        cursor.execute(
            "SELECT id_candado, num_casillero FROM candados WHERE estado ="
            " 'disponible' LIMIT 1"
        )
        candado = cursor.fetchone()

        if not candado:
          self.mostrar_resultado(
              "⚠️ SIN CANDADOS DISPONIBLES",
              "No quedan candados en el inventario.",
              [0.9, 0.29, 0.23, 1],
          )
          return

        c_id, cas_num = candado
        cursor.execute(
            "INSERT INTO prestamos (rut_alumno, id_candado) VALUES (?, ?)",
            (rut, c_id),
        )
        cursor.execute(
            "UPDATE candados SET estado = 'prestado' WHERE id_candado = ?",
            (c_id,),
        )
        cursor.execute(
            """
                    INSERT INTO solicitudes (rut, nombre, rol, carrera, accion, id_candado, num_casillero)
                    VALUES (?, ?, ?, ?, 'SOLICITUD', ?, ?)
                """,
            (rut, nombre, rol, carrera, c_id, cas_num),
        )
        conn.commit()

        self.mostrar_resultado(
            "✅ PRÉSTAMO AUTORIZADO",
            f"👤 Usuario: {nombre} [{rol}]\n🎓 Carrera: {carrera}\n\n🔑 CANDADO"
            f" ASIGNADO: {c_id} (Casillero: {cas_num})",
            [0.15, 0.68, 0.37, 1],
        )

    self.actualizar_estadisticas()

  def mostrar_resultado(self, titulo, detalle, color):
    self.root.ids.lbl_res_titulo.text = titulo
    self.root.ids.lbl_res_titulo.text_color = color
    self.root.ids.lbl_res_detalle.text = detalle

  def mostrar_modal_registro(self, rut):
    content = MDList()
    btn_guardar = MDRaisedButton(
        text="Guardar",
        on_release=lambda x: self.guardar_registro_rapido(rut, "NUEVO USER"),
    )
    self.dialog_registro = MDDialog(
        title=f"⚠️ RUT No Encontrado: {rut}",
        type="custom",
        content_cls=content,
        buttons=[
            MDFlatButton(
                text="Cancelar",
                on_release=lambda x: self.dialog_registro.dismiss(),
            ),
            btn_guardar,
        ],
    )
    self.dialog_registro.open()

  def guardar_registro_rapido(self, rut, nombre, rol="PERSONAL"):
    with sqlite3.connect("casilleros.db") as conn:
      cursor = conn.cursor()
      cursor.execute(
          """
                INSERT OR REPLACE INTO alumnos (rut, nombre, carrera, area, sede, periodo, carga, rol)
                VALUES (?, ?, 'Personal Institucional', 'Administración', 'LOS ÁNGELES', '2026', 'N/A', ?)
            """,
          (rut, nombre, rol),
      )
      conn.commit()
    if self.dialog_registro:
      self.dialog_registro.dismiss()
    self.procesar_escaneo(rut)

  def mostrar_ocupados(self):
    with sqlite3.connect("casilleros.db") as conn:
      cursor = conn.cursor()
      cursor.execute("""
                SELECT p.id_candado, c.num_casillero, a.nombre, COALESCE(a.rol, 'ESTUDIANTE')
                FROM prestamos p
                JOIN candados c ON p.id_candado = c.id_candado
                JOIN alumnos a ON p.rut_alumno = a.rut
                WHERE p.estado = 'activo'
            """)
      filas = cursor.fetchall()

    lista = MDList()
    for f in filas:
      lista.add_widget(
          TwoLineListItem(
              text=f"Candado {f[0]} (Casillero {f[1]})",
              secondary_text=f"{f[2]} [{f[3]}]",
          )
      )

    self.dialog_ocupados = MDDialog(
        title="📋 Candados Ocupados",
        type="confirmation",
        content_cls=lista,
        buttons=[
            MDFlatButton(
                text="Cerrar",
                on_release=lambda x: self.dialog_ocupados.dismiss(),
            )
        ],
    )
    self.dialog_ocupados.open()

  def enviar_informe_manual(self):
    threading.Thread(target=self._generar_y_enviar_email, daemon=True).start()

  def _generar_y_enviar_email(self):
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")
    with sqlite3.connect("casilleros.db") as conn:
      cursor = conn.cursor()
      cursor.execute(
          "SELECT COUNT(*) FROM solicitudes WHERE DATE(fecha_hora) ="
          " DATE('now', 'localtime') AND accion = 'SOLICITUD'"
      )
      tot_solicitudes = cursor.fetchone()[0]

    try:
      msg = MIMEMultipart()
      msg["From"] = CORREO_EMISOR
      msg["To"] = CORREO_DESTINATARIO
      msg["Subject"] = (
          f"📊 Reporte Diario de Casilleros - {fecha_hoy} ({tot_solicitudes}"
          " préstamos)"
      )
      msg.attach(
          MIMEText(
              f"Reporte de uso de casilleros del día {fecha_hoy}. Total"
              f" solicitudes: {tot_solicitudes}",
              "plain",
          )
      )

      server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
      server.starttls()
      server.login(CORREO_EMISOR, CORREO_PASSWORD)
      server.sendmail(CORREO_EMISOR, CORREO_DESTINATARIO, msg.as_string())
      server.quit()
    except Exception as e:
      print("Error al enviar email:", e)


if __name__ == "__main__":
  CasillerosApp().run()