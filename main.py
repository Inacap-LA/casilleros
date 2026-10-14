"""Interfaz KivyMD para el control institucional de préstamos de candados.

Versión corregida: lógica SQLite separada y envío de informe sin claves SMTP.
Requiere Kivy 2.3.0 y KivyMD 1.1.1.
"""

from datetime import datetime
import sqlite3
from urllib.parse import quote
import webbrowser

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.utils import platform

from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.list import MDList, TwoLineListItem
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.textfield import MDTextField

from database import (
    BusquedaAmbigua, GestorCasilleros, OperacionNoPermitida,
    normalizar_rut, obtener_ruta_db,
)

# Reemplazar por una casilla INSTITUCIONAL autorizada, nunca por una contraseña.
DESTINATARIO_INFORME = "destinatario_informe@empresa.cl"

KV = """
MDScreen:
    md_bg_color: 0.93, 0.95, 0.98, 1

    MDBoxLayout:
        orientation: 'vertical'

        MDTopAppBar:
            title: 'Control de Casilleros y Candados'
            elevation: 4
            right_action_items:
                [['table', lambda x: app.mostrar_ocupados()], ['email-send', lambda x: app.enviar_informe_manual()]]

        MDScrollView:
            MDBoxLayout:
                orientation: 'vertical'
                padding: '16dp'
                spacing: '16dp'
                size_hint_y: None
                height: self.minimum_height

                MDCard:
                    orientation: 'horizontal'
                    padding: '12dp'
                    spacing: '8dp'
                    size_hint_y: None
                    height: '72dp'
                    radius: [12,]
                    md_bg_color: 1, 1, 1, 1
                    elevation: 2

                    MDLabel:
                        id: lbl_disp
                        text: 'Disponibles: --'
                        bold: True
                        theme_text_color: 'Custom'
                        text_color: 0.15, 0.68, 0.37, 1
                        halign: 'center'
                        font_style: 'Caption'

                    MDLabel:
                        id: lbl_prest
                        text: 'Prestados: --'
                        bold: True
                        theme_text_color: 'Custom'
                        text_color: 0.9, 0.29, 0.23, 1
                        halign: 'center'
                        font_style: 'Caption'

                    MDLabel:
                        id: lbl_mov
                        text: 'Movimientos hoy: --'
                        bold: True
                        theme_text_color: 'Custom'
                        text_color: 0.16, 0.5, 0.73, 1
                        halign: 'center'
                        font_style: 'Caption'

                MDCard:
                    orientation: 'vertical'
                    padding: '16dp'
                    spacing: '10dp'
                    size_hint_y: None
                    height: '112dp'
                    radius: [12,]
                    elevation: 2

                    MDLabel:
                        text: 'Seleccione operación:'
                        font_style: 'Subtitle1'
                        bold: True

                    MDBoxLayout:
                        spacing: '8dp'

                        MDRaisedButton:
                            id: btn_solicitar
                            text: 'SOLICITAR'
                            size_hint_x: 0.5
                            md_bg_color: 0.15, 0.68, 0.37, 1
                            on_release: app.set_modo('SOLICITAR')

                        MDRaisedButton:
                            id: btn_devolver
                            text: 'DEVOLVER'
                            size_hint_x: 0.5
                            md_bg_color: 0.6, 0.6, 0.6, 1
                            on_release: app.set_modo('DEVOLVER')

                MDCard:
                    orientation: 'vertical'
                    padding: '16dp'
                    spacing: '8dp'
                    size_hint_y: None
                    height: '122dp'
                    radius: [12,]
                    elevation: 2

                    MDTextField:
                        id: txt_rut
                        hint_text: 'Escanee carnet o ingrese RUT / Nombre'
                        helper_text: 'Presione Enter para buscar'
                        helper_text_mode: 'persistent'
                        font_size: '18sp'
                        multiline: False
                        on_text_validate: app.procesar_escaneo(self.text)

                MDCard:
                    orientation: 'vertical'
                    padding: '20dp'
                    spacing: '10dp'
                    size_hint_y: None
                    height: '290dp'
                    radius: [12,]
                    md_bg_color: 1, 1, 1, 1
                    elevation: 2

                    MDLabel:
                        id: lbl_res_titulo
                        text: 'ESPERANDO LECTURA'
                        font_style: 'H6'
                        bold: True
                        theme_text_color: 'Custom'
                        text_color: 0.5, 0.5, 0.5, 1
                        size_hint_y: None
                        height: '48dp'

                    MDSeparator:

                    MDLabel:
                        id: lbl_res_detalle
                        text: 'Seleccione la operación y escanee el carnet con su lector USB/Bluetooth.'
                        font_style: 'Body1'
                        valign: 'top'
"""


class CasillerosApp(MDApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.db = GestorCasilleros(obtener_ruta_db())
        self.modo_actual = "SOLICITAR"
        self.dialog_registro = None
        self.dialog_ocupados = None

    def build(self):
        self.theme_cls.primary_palette = "Blue"
        self.db.inicializar()
        pantalla = Builder.load_string(KV)
        Clock.schedule_once(lambda dt: self.actualizar_estadisticas(), 0.5)
        Clock.schedule_once(lambda dt: self._enfocar_rut(), 0.75)
        return pantalla

    def _enfocar_rut(self):
        if self.root:
            self.root.ids.txt_rut.focus = True

    def set_modo(self, modo):
        if modo not in ("SOLICITAR", "DEVOLVER"):
            return
        self.modo_actual = modo
        self.root.ids.btn_solicitar.md_bg_color = (
            [0.15, 0.68, 0.37, 1] if modo == "SOLICITAR" else [0.6, 0.6, 0.6, 1]
        )
        self.root.ids.btn_devolver.md_bg_color = (
            [0.16, 0.5, 0.73, 1] if modo == "DEVOLVER" else [0.6, 0.6, 0.6, 1]
        )
        self._enfocar_rut()

    def actualizar_estadisticas(self):
        try:
            valores = self.db.estadisticas()
            self.root.ids.lbl_disp.text = "Disponibles: {}".format(valores["disponibles"])
            self.root.ids.lbl_prest.text = "Prestados: {}".format(valores["prestados"])
            self.root.ids.lbl_mov.text = "Movimientos hoy: {}".format(valores["movimientos_hoy"])
        except Exception as error:
            self.mostrar_resultado("ERROR DE BASE DE DATOS", str(error), [0.9, 0.29, 0.23, 1])

    def mostrar_resultado(self, titulo, detalle, color):
        self.root.ids.lbl_res_titulo.text = titulo
        self.root.ids.lbl_res_titulo.text_color = color
        self.root.ids.lbl_res_detalle.text = detalle

    def _ejecutar_operacion(self, rut):
        if self.modo_actual == "SOLICITAR":
            resultado = self.db.solicitar(rut)
            titulo = "PRÉSTAMO AUTORIZADO"
            color = [0.15, 0.68, 0.37, 1]
            estado = "ASIGNADO"
        else:
            resultado = self.db.devolver(rut)
            titulo = "DEVOLUCIÓN REGISTRADA"
            color = [0.16, 0.5, 0.73, 1]
            estado = "LIBERADO"
        detalle = (
            "Usuario: {} [{}]\nCarrera: {}\n\nCandado {}: {}\nCasillero: {}".format(
                resultado["nombre"], resultado["rol"], resultado["carrera"],
                estado, resultado["id_candado"], resultado["num_casillero"]
            )
        )
        self.mostrar_resultado(titulo, detalle, color)
        self.actualizar_estadisticas()

    def procesar_escaneo(self, texto):
        criterio = (texto or "").strip()
        self.root.ids.txt_rut.text = ""
        if not criterio:
            return
        try:
            persona = self.db.buscar_persona(criterio)
            if persona is None:
                self.mostrar_modal_registro(criterio)
                return
            self._ejecutar_operacion(persona["rut"])
        except (OperacionNoPermitida, BusquedaAmbigua) as error:
            self.mostrar_resultado("OPERACIÓN NO REALIZADA", str(error), [0.9, 0.29, 0.23, 1])
        except Exception as error:
            self.mostrar_resultado("ERROR INESPERADO", str(error), [0.9, 0.29, 0.23, 1])
        finally:
            Clock.schedule_once(lambda dt: self._enfocar_rut(), 0.3)

    def mostrar_modal_registro(self, rut):
        if self.modo_actual == "DEVOLVER":
            self.mostrar_resultado(
                "USUARIO NO ENCONTRADO", "No se puede devolver sin usuario registrado.",
                [0.9, 0.29, 0.23, 1]
            )
            return
        caja = MDBoxLayout(orientation="vertical", spacing="8dp", size_hint_y=None,
                           height="150dp")
        txt_rut = MDTextField(hint_text="RUT / RUN", text=normalizar_rut(rut))
        txt_nombre = MDTextField(hint_text="Nombre y apellidos")
        txt_carrera = MDTextField(hint_text="Carrera / Departamento",
                                  text="Personal Institucional")
        for campo in (txt_rut, txt_nombre, txt_carrera):
            caja.add_widget(campo)

        def guardar(_):
            try:
                nuevo_rut = self.db.registrar_persona(txt_rut.text, txt_nombre.text,
                                                      txt_carrera.text)
                self.dialog_registro.dismiss()
                self.dialog_registro = None
                self._ejecutar_operacion(nuevo_rut)
            except (OperacionNoPermitida, sqlite3.IntegrityError) as error:
                self.mostrar_resultado("REGISTRO NO REALIZADO", str(error), [0.9, 0.29, 0.23, 1])
            except Exception as error:
                self.mostrar_resultado("ERROR DE REGISTRO", str(error), [0.9, 0.29, 0.23, 1])

        def cancelar(_):
            self.dialog_registro.dismiss()
            self.dialog_registro = None
            self._enfocar_rut()

        self.dialog_registro = MDDialog(
            title="Registrar usuario nuevo",
            type="custom",
            content_cls=caja,
            buttons=[
                MDFlatButton(text="CANCELAR", on_release=cancelar),
                MDFlatButton(text="REGISTRAR Y SOLICITAR", on_release=guardar),
            ],
        )
        self.dialog_registro.open()

    def mostrar_ocupados(self):
        try:
            ocupados = self.db.ocupados()
        except Exception as error:
            self.mostrar_resultado("ERROR AL CONSULTAR", str(error), [0.9, 0.29, 0.23, 1])
            return
        lista = MDList()
        if ocupados:
            for registro in ocupados:
                lista.add_widget(TwoLineListItem(
                    text="Casillero {} - Candado {}".format(
                        registro["num_casillero"], registro["id_candado"]),
                    secondary_text="{} | {}".format(
                        registro["nombre"], registro["carrera"]),
                ))
        else:
            lista.add_widget(TwoLineListItem(
                text="No existen préstamos activos", secondary_text="Todos los candados están disponibles"
            ))
        scroller = MDScrollView(size_hint_y=None, height="350dp")
        scroller.add_widget(lista)

        def cerrar(_):
            self.dialog_ocupados.dismiss()
            self.dialog_ocupados = None
            self._enfocar_rut()

        self.dialog_ocupados = MDDialog(
            title="Candados ocupados ({})".format(len(ocupados)),
            type="custom", content_cls=scroller,
            buttons=[MDFlatButton(text="CERRAR", on_release=cerrar)],
        )
        self.dialog_ocupados.open()

    def enviar_informe_manual(self):
        """Abre el correo del usuario. Nunca almacena contraseñas SMTP en el APK."""
        if "@" not in DESTINATARIO_INFORME or DESTINATARIO_INFORME.startswith("destinatario_"):
            self.mostrar_resultado(
                "FALTA CONFIGURAR DESTINATARIO",
                "Modifique DESTINATARIO_INFORME en main.py antes de enviar correos.",
                [0.9, 0.29, 0.23, 1],
            )
            return
        try:
            informe = self.db.informe_texto()
            asunto = "Informe de candados - {}".format(datetime.now().strftime("%d-%m-%Y %H:%M"))
            if platform == "android":
                from jnius import autoclass
                Intent = autoclass("android.content.Intent")
                Uri = autoclass("android.net.Uri")
                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                intent = Intent(Intent.ACTION_SENDTO)
                intent.setData(Uri.parse("mailto:" + DESTINATARIO_INFORME))
                intent.putExtra(Intent.EXTRA_SUBJECT, asunto)
                intent.putExtra(Intent.EXTRA_TEXT, informe)
                PythonActivity.mActivity.startActivity(Intent.createChooser(intent, "Enviar informe"))
            else:
                # mailto admite textos cortos: el informe completo se mantiene en Android.
                resumen = "\n".join(informe.splitlines()[:18])
                url = "mailto:{}?subject={}&body={}".format(
                    quote(DESTINATARIO_INFORME), quote(asunto), quote(resumen))
                if not webbrowser.open(url):
                    raise RuntimeError("No se encontró una aplicación de correo predeterminada.")
            self.mostrar_resultado(
                "INFORME PREPARADO",
                "Se abrió el correo para que revise y confirme el envío.",
                [0.16, 0.5, 0.73, 1],
            )
        except Exception as error:
            self.mostrar_resultado(
                "NO SE PUDO ABRIR EL CORREO", str(error), [0.9, 0.29, 0.23, 1]
            )


if __name__ == "__main__":
    CasillerosApp().run()
