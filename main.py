import os
import shutil
import smtplib
import sqlite3
import threading
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.utils import platform

from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.list import MDList, TwoLineListItem
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.textfield import MDTextField

# ==============================================================================
# CONFIGURACIÓN DE CORREO ELECTRÓNICO PARA INFORMES
# ==============================================================================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
CORREO_EMISOR = "tu_correo@gmail.com"
CORREO_PASSWORD = "tu_clave_de_aplicacion"
CORREO_DESTINATARIO = "destinatario_informe@empresa.cl"


def get_db_path():
  """Obtiene la ruta adecuada de la Base de Datos para PC o Android (APK)."""
  db_name = "casilleros.db"

  if platform == "android":
    try:
      from android.storage import app_storage_path

      app_dir = app_storage_path()
      target_path = os.path.join(app_dir, db_name)

      # Si no existe en la memoria privada de Android, la copiamos desde los Assets
      if not os.path.exists(target_path):
        if os.path.exists(db_name):
          shutil.copyfile(db_name, target_path)
        elif os.path.exists(os.path.join(os.path.dirname(__file__), db_name)):
          shutil.copyfile(
              os.path.join(os.path.dirname(__file__), db_name), target_path
          )
      return target_path
    except Exception as e:
      print(f"Error detectando ruta Android: {e}")
      return db_name
  return db_name


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
    self.db_path = get_db_path()
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
    """Verifica e inicializa la estructura de la base de datos."""
    with sqlite3.connect(self.db_path) as conn:
      cursor = conn.cursor()
      cursor.execute("PRAGMA foreign_keys = ON;")

      # Intenta agregar la columna rol si no existe
      try:
        cursor.execute(
            "ALTER TABLE alumnos ADD COLUMN rol TEXT DEFAULT 'ESTUDIANTE'"
        )
      except sqlite3.OperationalError:
        pass

      # Tabla de bitácora/solicitudes
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
    with sqlite3.connect(self.db_path) as conn:
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

    with sqlite3.connect(self.db_path) as conn:
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
            " = 'devuelto' WHERE id = ?",
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
              f" {cas_num}).",
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
    """Modal interactivo para registrar un usuario no encontrado."""
    box = MDBoxLayout(
        orientation="vertical", spacing="10dp", size_hint_y=None, height="120dp"
    )
    txt_nombre = MDTextField(
        hint_text="Nombre y Apellidos", font_size="16sp"
    )
    txt_carrera = MDTextField(
        hint_text="Carrera / Departamento",
        text="Personal Institucional",
        font_size="16sp",
    )
    box.add_widget(txt_nombre)
    box.add_widget(txt_carrera)

    def guardar_accion(x):
      nom = txt_nombre.text.strip() or f"Usuario {rut}"
      car = txt_carrera.text.strip() or "Personal Institucional"
      self.guardar_registro
