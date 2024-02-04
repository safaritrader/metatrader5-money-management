import os
import sys
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication, QFileDialog, QMainWindow, QTableWidgetItem, QVBoxLayout, QTreeWidgetItem, \
    QLabel, QFrame, QPushButton, QTextEdit
from interface_v2 import Ui_Form
import json
import MetaTrader5 as mt5
from PyQt6.QtCore import QTimer, Qt, QSize, QRect, QUrl
from PyQt6.QtGui import QColor, QBrush, QIcon
from PyQt6.QtMultimedia import QSoundEffect
from pathlib import Path
import requests
import pandas as pd
import io
from threading import Thread
import time
from datetime import datetime, timedelta
from pyqtgraph.widgets.PlotWidget import PlotWidget
from pyqtgraph import mkPen, InfiniteLine, PlotCurveItem
import pyqtgraph as pg
from pyqtgraph import QtCore as qtc
from pyqtgraph import QtGui as qtg
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import ctypes

pg.setConfigOptions(antialias=True, leftButtonPan=False, crashWarning=True, exitCleanup=False)


class CandlestickItem(pg.GraphicsObject):
    def __init__(self, data):
        pg.GraphicsObject.__init__(self)
        self.data = data
        self.generatePicture()

    def generatePicture(self):
        self.picture = qtg.QPicture()
        p = qtg.QPainter(self.picture)
        p.setPen(pg.mkPen('w'))
        w = (self.data[1][0] - self.data[0][0]) / 3.
        for (t, open1, close1, min1, max1) in self.data:
            p.drawLine(qtc.QPointF(t, min1), qtc.QPointF(t, max1))
            if open1 > close1:
                p.setBrush(pg.mkBrush('r'))
            else:
                p.setBrush(pg.mkBrush('g'))
            p.drawRect(qtc.QRectF(t - w, open1, w * 2, close1 - open1))
        p.end()

    def paint(self, p, *args):
        p.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        return qtc.QRectF(self.picture.boundingRect())


class Window(QMainWindow):
    def __init__(self):
        super().__init__()

        self.magic = 2301
        # 123230450
        self.userid = 123456
        # use the Ui_login_form
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        icon = QIcon("img/icon.png")
        # set the icon for the window
        self.setWindowIcon(icon)
        # Save And Load Data
        self.ui.save_b.clicked.connect(self.save_info)
        self.ui.load_b.clicked.connect(self.load_info)

        # Start
        self.mt5 = mt5
        self.flag = False
        self.ui.start_b.clicked.connect(self.start)
        # Trade
        self.symbol = 'XAUUSD'
        self.ui.buy.clicked.connect(self.buy)
        self.ui.halfbuy.clicked.connect(self.halfbuy)
        self.ui.sell.clicked.connect(self.sell)
        self.ui.halfsell.clicked.connect(self.halfsell)
        self.ui.freerisk_b.clicked.connect(self.freerisk)
        self.ui.close1_b.clicked.connect(self.closepct)
        self.ui.close2_b.clicked.connect(self.closepct2)
        self.ui.closall_b.clicked.connect(self.closeall)
        self.trade = True
        # Detailes
        self.t1 = ''
        self.dec = {
            '1': 10,
            '2': 100,
            '3': 1000,
            '4': 10000,
            '5': 100000,
            '6': 1000000,
            '7': 10000000
        }
        self.ret = {
            "10004": "Requote",
            "10006": "Request rejected",
            "10007": "Request canceled by trader",
            "10008": "Order placed",
            "10009": "Request completed",
            "10010": "Only part of the request was completed",
            "10011": "Request processing error",
            "10012": "Request canceled by timeout",
            "10013": "Invalid request",
            "10014": "Invalid volume in the request",
            "10015": "Invalid price in the request",
            "10016": "Invalid stops in the request",
            "10017": "Trade is disabled",
            "10018": "<red>Market is closed</red>",
            "10019": "There is not enough money to complete the request",
            "10020": "Prices changed",
            "10021": "There are no quotes to process the request",
            "10022": "Invalid order expiration date in the request",
            "10023": "Order state changed",
            "10024": "Too frequent requests",
            "10025": "No changes in request",
            "10026": "Autotrading disabled by server",
            "10027": "Autotrading disabled by client terminal",
            "10028": "Request locked for processing",
            "10029": "Order or position frozen",
            "10030": "Invalid order filling type",
            "10031": "No connection with the trade server",
            "10032": "Operation is allowed only for live accounts",
            "10033": "The number of pending orders has reached the limit",
            "10034": "The volume of orders and positions for the symbol has reached the limit",
            "10035": "Incorrect or prohibited order type",
            "10036": "Position with the specified POSITION_IDENTIFIER has already been closed",
            "10038": "A close volume exceeds the current position volume",
            "10039": "A close order already exists for a specified position. This may happen when "
                     "working in the hedging system",
            "10040": "The number of open positions simultaneously present on an account can be"
                     " limited by the server settings.",
            "10041": "The pending order activation request is rejected, the order is canceled",
            "10042": "The request is rejected, because the Only long positions are allowed rule"
                     " is set for the symbol (POSITION_TYPE_BUY)",
            "10043": "The request is rejected, because the Only short positions are allowed rule"
                     " is set for the symbol (POSITION_TYPE_SELL)",
            "10044": "The request is rejected, because the Only position closing is allowed rule"
                     " is set for the symbol ",
            "10045": "The request is rejected, because Position closing is allowed only by FIFO"
                     " rule flag is set for the trading account (ACCOUNT_FIFO_CLOSE=true)",
            "10046": "The request is rejected, because the Opposite positions on a single symbol "
                     "are disabled rule is set for the trading account. ",

        }
        # Threads and Timers
        self.prof = QTimer()
        self.prof.setInterval(100)
        self.prof.timeout.connect(self.set_prof)
        self.prof.start()
        self.t1 = Thread(target=self.calendar)
        self.t1.daemon = True
        self.t1.start()

        self.t2 = Thread(target=self.set_img)
        self.t2.daemon = True
        self.t2.start()
        self.calendar_e = True
        # Chart and Calendar Set
        self.ui.nownews_l.hide()
        self.ui.show_calendar_b.hide()
        self.ui.chart_frame.hide()
        self.ui.chart_frame.hide()
        self.ui.show_chart_b.clicked.connect(self.show_chart)
        self.ui.show_calendar_b.clicked.connect(self.show_calendar)

        # Create a plot widget
        self.plot_widget = PlotWidget(parent=self.ui.show_chart_f)
        self.square = None
        self.candle = None
        self.line = None
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.plot_widget)
        # set the layout for the parent widget
        self.ui.show_chart_f.setLayout(self.layout)
        # Connect the mouse click event of the plot widget to a custom slot
        self.plot_widget.scene().sigMouseClicked.connect(self.on_mouse_click_chart)
        self.chart_updater_timer = QTimer()
        self.chart_updater_timer.setInterval(500)
        self.chart_updater_timer.timeout.connect(self.chart_updater)
        self.ui.show_chart_ch.clicked.connect(self.chk)
        self.set_sl = False
        self.min_sl_buff = ""
        self.main_profit = 0
        self.RRs = {
            'RR1': {},
            'RR2': {}
        }
        self.ui.RR1.clicked.connect(self.RR1_chk)
        self.rr1_timer = QTimer()
        self.rr1_timer.setInterval(10)
        self.rr1_timer.timeout.connect(self.RR1)

        self.ui.RR2.clicked.connect(self.RR2_chk)
        self.rr2_timer = QTimer()
        self.rr2_timer.setInterval(10)
        self.rr2_timer.timeout.connect(self.RR2)

        self.ui.pos_tree.setColumnWidth(1, 0)
        self.ui.pos_tree.itemClicked.connect(self.pos_click)

        self.pos_time = QTimer()
        self.pos_time.setInterval(10)
        self.pos_time.timeout.connect(self.uptable)

        self.start_balance = 0
        self.ticket_current_symbol = 0

        self.lbl = QLabel(self)
        self.lbl.hide()
        self.pixmap_imgs = QPixmap()
        self.ui.show_statement_b.clicked.connect(self.show_statement)

        # Info Buttons
        self.info_icon = QIcon(r"img/info.png")

        self.info_stage_1 = QPushButton(self)
        self.info_stage_1.setGeometry(QRect(490, 9, 20, 20))
        self.info_stage_1.setIcon(self.info_icon)
        self.info_stage_1.setIconSize(QSize(15, 15))
        self.info_stage_1.clicked.connect(lambda: self.show_info_stage(1))
        self.info_stage_1.setStyleSheet('border:0px;background-color:rgba(0,0,0,0);')
        self.info_stage_5 = QPushButton(self)
        self.info_stage_5.setGeometry(QRect(493, 288, 20, 20))
        self.info_stage_5.setIcon(self.info_icon)
        self.info_stage_5.setIconSize(QSize(15, 15))
        self.info_stage_5.clicked.connect(lambda: self.show_info_stage(5))
        self.info_stage_5.setStyleSheet('border:0px;background-color:rgba(0,0,0,0);')
        self.info_stage_6 = QPushButton(self)
        self.info_stage_6.setGeometry(QRect(493, 398, 20, 20))
        self.info_stage_6.setIcon(self.info_icon)
        self.info_stage_6.setIconSize(QSize(15, 15))
        self.info_stage_6.clicked.connect(lambda: self.show_info_stage(6))
        self.info_stage_6.setStyleSheet('border:0px;background-color:rgba(0,0,0,0);')
        self.info_stage_9 = QPushButton(self)
        self.info_stage_9.setGeometry(QRect(222, 149, 20, 20))
        self.info_stage_9.setIcon(self.info_icon)
        self.info_stage_9.setIconSize(QSize(15, 15))
        self.info_stage_9.clicked.connect(lambda: self.show_info_stage(9))
        self.info_stage_9.setStyleSheet('border:0px;background-color:rgba(0,0,0,0);')

        self.sound_icon = QIcon(r"img/sound_on.png")
        self.mute_icon = QIcon(r'img/sound_off.png')
        self.sound_trade = QPushButton(self)
        self.sound_trade.setGeometry(QRect(221, 10, 20, 20))
        self.sound_trade.setIcon(self.sound_icon)
        self.sound_trade.setIconSize(QSize(15, 15))
        self.sound_trade.clicked.connect(lambda: self.mute_sound('trade'))
        self.sound_trade.setStyleSheet('border:0px;background-color:rgba(0,0,0,0);')

        self.sound_news = QPushButton(self)
        self.sound_news.setGeometry(QRect(7, 400, 20, 20))
        self.sound_news.setIcon(self.sound_icon)
        self.sound_news.setIconSize(QSize(15, 15))
        self.sound_news.clicked.connect(lambda: self.mute_sound('news'))
        self.sound_news.setStyleSheet('border:0px;background-color:rgba(0,0,0,0);')
        # Tutorial Section
        self.t_stage = 0
        self.t_text_index = 0
        self.t_text = ''
        self.t_frame = QFrame(self)
        self.t_frame.setGeometry(QRect(0, 0, 461, 141))
        self.t_frame.setObjectName('t_frame')
        self.t_frame.setStyleSheet('#t_frame{background-color: rgba(255, 255, 255, 1);border: 1px dashed black;}')
        self.t_logo = QPushButton(parent=self.t_frame)
        self.t_logo.setGeometry(QRect(0, 20, 102, 100))
        self.t_logo_i = QIcon('img/icon.png')
        self.t_logo.setIcon(self.t_logo_i)
        self.t_logo.setIconSize(QSize(100, 100))
        self.t_logo.setStyleSheet('background-color: rgba(255, 255, 255, 0);border-color: rgba(255, 255, 255,0);')
        self.t_text_edit = QTextEdit(parent=self.t_frame)
        self.t_text_edit.setGeometry(QRect(110, 5, 341, 111))
        self.t_prev_b = QPushButton(parent=self.t_frame)
        self.t_prev_b.setGeometry(QRect(110, 116, 51, 23))
        self.t_prev_b.setStyleSheet('background-color: grey;color:white;')
        self.t_prev_b.setText('<')
        self.t_prev_b.clicked.connect(lambda: self.t_action('previous'))
        self.t_close_b = QPushButton(parent=self.t_frame)
        self.t_close_b.setGeometry(QRect(250, 116, 51, 23))
        self.t_close_b.setText('*')
        self.t_close_b.clicked.connect(lambda: self.t_action('close'))
        self.t_next_b = QPushButton(parent=self.t_frame)
        self.t_next_b.setGeometry(QRect(400, 116, 51, 23))
        self.t_next_b.setText('>')
        self.t_next_b.setStyleSheet('background-color: rgb(45, 137, 239);color:white;')
        self.t_next_b.clicked.connect(lambda: self.t_action('next'))
        # self.t_frame.hide()
        self.t_arrow = QPushButton(self)
        self.t_arrow.setGeometry(QRect(0, 0, 102, 100))
        self.t_arrow.setStyleSheet('background-color: rgba(255, 255, 255, 0);border-color: rgba(255, 255, 255,0);')

        self.t_typer = QTimer()
        self.t_typer.setInterval(40)
        self.t_typer.timeout.connect(self.tutorial_typer)

        self.wlc = QSoundEffect(self)
        abs_path = os.path.abspath(r".\\img\sounds\welcome.wav")
        self.wlc.setSource(QUrl.fromLocalFile(abs_path))
        self.wlc.setLoopCount(1)
        self.wlc.setVolume(1)

        self.click_sound = QSoundEffect(self)
        abs_path = os.path.abspath(r".\\img\sounds\click.wav")
        self.click_sound.setSource(QUrl.fromLocalFile(abs_path))
        self.click_sound.setLoopCount(1)
        self.click_sound.setVolume(1)

        self.news_sound_alert = QSoundEffect(self)
        abs_path = os.path.abspath(r".\\img\sounds\news_alert.wav")
        self.news_sound_alert.setSource(QUrl.fromLocalFile(abs_path))
        self.news_sound_alert.setVolume(1)

        self.sound_player_timer = QTimer()
        self.sound_player_timer.setInterval(10)
        self.sound_player_timer.timeout.connect(self.sound_player)
        self.sound_player_timer.start()
        self.sound = ""
        self.welcome_playing = True
        self.tutorial_data = None

        self.time_news = []
        try:
            with open("tutorial.json", 'r') as f:
                t = json.load(f)
            if t['state'] == 'Not Learned':
                self.start_tutorial()
            else:
                self.t_frame.hide()
                self.t_arrow.hide()
                self.tutorial_data = t
        except Exception as error:
            print(error)

        # self.installEventFilter(self)

        self.ui.mt5terminalpath_t.setText(r'C:\Program Files\MetaTrader\terminal64.exe')
        self.show()

    # def eventFilter(self, obj, event):
    #     if obj is self and event.type() == QEvent.Type.MouseButtonPress:
    #         self.clearFocus()
    #         # clear selection in table and text widgets
    #         print(obj , print(event.type()))
    #     return super().eventFilter(obj, event)
    def sound_player(self):
        """
        play sound
        :return:
        """
        if self.sound == "news":
            self.news_sound_alert.play()
            self.sound = ""

    def mute_sound(self, which):
        """
        select sound and mute them
        :param which:
        :return:
        """
        if which == 'trade':
            if self.click_sound.isMuted():
                self.click_sound.setMuted(False)
                self.sound_trade.setIcon(self.sound_icon)
            else:
                self.click_sound.setMuted(True)
                self.sound_trade.setIcon(self.mute_icon)
        elif which == 'news':
            if self.news_sound_alert.isMuted():
                self.news_sound_alert.setMuted(False)
                self.sound_news.setIcon(self.sound_icon)
            else:
                self.news_sound_alert.setMuted(True)
                self.sound_news.setIcon(self.mute_icon)
        # self.sound_news

    def show_info_stage(self, stg):
        """
        start tutorial
        :param stg:
        :return:
        """
        self.t_text_edit.setPlainText('')
        self.t_stage = stg
        self.start_tutorial()

    def tutorial_typer(self):
        """
        typer for tutorial in textbox
        :return:
        """
        if self.t_stage == 0 and self.welcome_playing:
            self.wlc.play()
            self.welcome_playing = False
            print('played')
        if self.t_text_index < len(self.t_text):
            self.t_text_edit.setPlainText(self.t_text_edit.toPlainText() + self.t_text[self.t_text_index])
            self.t_text_index += 1
        else:
            self.t_text_index += 1
            self.t_typer.stop()

    def t_action(self, act):
        """
        action buttons next or back
        :param act:
        :return:
        """
        if act == 'next':
            if self.t_stage + 1 <= 10:
                self.t_text_edit.setPlainText('')
                self.t_stage += 1
                self.start_tutorial()
            if self.t_stage == 10:
                self.tutorial_data['state'] = 'Learned'
                with open("tutorial.json", "w") as f:
                    json.dump(self.tutorial_data, f, indent=4)
        elif act == 'previous':
            if self.t_stage - 1 >= 1:
                self.t_text_edit.setPlainText('')
                self.t_stage -= 1
                self.start_tutorial()
        elif act == 'close':
            self.t_text_edit.setPlainText('')
            self.t_arrow.hide()
            self.t_frame.hide()
            if self.t_stage == 10:
                self.tutorial_data['state'] = 'Learned'
                with open("tutorial.json", "w") as f:
                    json.dump(self.tutorial_data, f, indent=4)

    def start_tutorial(self):
        """
        start tutorial
        :return:
        """
        try:
            self.t_typer.stop()
            if self.tutorial_data is None:
                with open("tutorial.json", 'r') as f:
                    t = json.load(f)
                # print(t)
                self.tutorial_data = t
            f_pos = self.tutorial_data[f'stage{self.t_stage}']['frames_pos']

            a_pos = self.tutorial_data[f'stage{self.t_stage}']['arrow_pos']
            self.t_frame.setGeometry(QRect(f_pos[0], f_pos[1], f_pos[2], f_pos[3]))
            if self.t_stage != 0:
                self.t_arrow.setGeometry(QRect(a_pos[0], a_pos[1], a_pos[2], a_pos[3]))
            icon = self.tutorial_data[f'stage{self.t_stage}']['arrow']
            icl = QIcon(fr"img/arrows/{icon}.png")
            self.t_arrow.setIcon(icl)
            self.t_arrow.setIconSize(QSize(100, 100))
            if self.t_stage != 0:
                self.t_arrow.show()
            self.t_frame.show()
            self.t_text = self.tutorial_data[f'stage{self.t_stage}']['text']
            self.t_text_index = 0
            self.t_typer.start()
        except Exception as error:
            print(error)

    def show_statement(self):
        """
        show statement
        :return:
        """
        if self.ui.show_statement_b.text() == "Statement":
            if self.mt5.last_error()[1] != 'No IPC connection' and self.mt5.last_error()[1] != '':

                from1 = datetime.today().strftime("%d/%m/%Y")
                from1 = datetime.strptime(from1, "%d/%m/%Y")
                poss = self.mt5.history_deals_get(from1 - timedelta(days=0), from1 + timedelta(days=1))
                if len(poss) >= 1:
                    ps = {}
                    for i in range(0, len(poss)):

                        if str(poss[i].ticket) in ps:
                            pass
                        else:
                            ps[f'{poss[i].ticket}'] = {}
                            ps[f'{poss[i].ticket}']['time'] = time.strftime("%Y-%m-%d %H:%M:%S",
                                                                            time.gmtime(poss[i].time))
                            ps[f'{poss[i].ticket}']['profit'] = poss[i].profit
                            ps[f'{poss[i].ticket}']['type'] = "buy" if poss[i].type == 1 else "sell"
                    ps = {k: v for k, v in ps.items() if (v['profit'] != 0)}
                    ind = []
                    profit = []
                    win = 0
                    total = 0
                    loss = 0
                    gain = 0
                    for k, v in ps.items():
                        ind.append(v['time'])
                        profit.append(v['profit'])
                        total += 1
                        if v['profit'] >= 0:
                            win += 1
                            gain += v['profit']
                        else:
                            loss += v['profit']
                    df = pd.DataFrame()
                    df['time'] = ind
                    df['profit'] = profit
                    minn = float(df['profit'].min())
                    fig = make_subplots(rows=1, cols=1, shared_xaxes=True,
                                        specs=[[{'type': 'scatter'}]],
                                        vertical_spacing=0.01,
                                        row_heights=[1])
                    fig.add_trace(go.Scatter(name="Sum : ", x=df.index, y=df['profit'].cumsum(), mode='lines+markers',
                                             marker=dict(color="Blue", size=4)),
                                  row=1, col=1)
                    balance = float(self.start_balance)
                    drawdown = round(minn / balance * 100, 2)
                    color = "red" if drawdown < 0 else "black"
                    draft_template = go.layout.Template()
                    draft_template.layout.annotations = [
                        dict(
                            name="Details",
                            text=f"Win Rate : %{round(win / total * 100, 2)} | Max DrawDown:"
                                 f" <span style='color:{color}'>%{drawdown}</span>"
                                 f" | RR : {round(gain / abs(loss), 2)}",
                            textangle=-0,
                            opacity=1,
                            font=dict(color="#000", size=13),
                            xref="paper",
                            yref="paper",
                            x=0,
                            y=0,
                            showarrow=False,
                        )
                    ]
                    fig.update_layout(
                        template=draft_template,
                        xaxis_rangeslider_visible=False,
                        height=141,
                        width=421,
                        margin=dict(
                            l=0,
                            r=0,
                            b=0,
                            t=0,
                            pad=0),
                        showlegend=False,
                        plot_bgcolor="#FFFFFF",
                        paper_bgcolor="#FFFFFF",
                        bargap=0,
                        bargroupgap=0,
                        yaxis_tickformat='$',

                    )
                    for i in range(2, 0, -1):
                        fig.update_xaxes(row=i, col=1, rangeslider_visible=False)
                    fig.update_xaxes(gridcolor="#DCDCDC", showspikes=True)
                    fig.update_yaxes(gridcolor="#DCDCDC", automargin=True, showspikes=True, side="right", nticks=7)
                    fig.write_image("statement.jpeg")
                    self.pixmap_imgs.load("statement.jpeg")
                    pixmap = self.pixmap_imgs.scaled(QSize(421, 141), Qt.AspectRatioMode.KeepAspectRatio,
                                                     Qt.TransformationMode.SmoothTransformation)
                    self.lbl.setPixmap(pixmap)
                    self.lbl.show()
                    self.layout.replaceWidget(self.layout.itemAt(0).widget(), self.lbl)
                    self.ui.show_chart_f.setLayout(self.layout)
                else:
                    self.pixmap_imgs.load("img/noposition.png")
                    pixmap = self.pixmap_imgs.scaled(QSize(421, 141), Qt.AspectRatioMode.KeepAspectRatio,
                                                     Qt.TransformationMode.SmoothTransformation)
                    self.lbl.setPixmap(pixmap)
                    self.lbl.show()
                    self.layout.replaceWidget(self.layout.itemAt(0).widget(), self.lbl)
                    self.ui.show_chart_f.setLayout(self.layout)
            else:
                self.pixmap_imgs.load("img/dissconnect.png")
                pixmap = self.pixmap_imgs.scaled(QSize(421, 141), Qt.AspectRatioMode.KeepAspectRatio,
                                                 Qt.TransformationMode.SmoothTransformation)
                self.lbl.setPixmap(pixmap)
                self.lbl.show()
                self.layout.replaceWidget(self.layout.itemAt(0).widget(), self.lbl)
                self.ui.show_chart_f.setLayout(self.layout)
            self.ui.show_statement_b.setText('Hide')
        else:
            self.show_chart()
            self.ui.show_statement_b.setText("Statement")
        pass

    def clear_tree_selection(self):
        """
        clear selection of symbol
        :return:
        """
        self.ui.pos_tree.clearSelection()
        self.ticket_current_symbol = 0

    def pos_click(self, item, column):
        """
        pos click
        :param item:
        :param column:
        :return:
        """
        self.ticket_current_symbol = float(item.text(1))

    def uptable(self):
        """
        update table
        :return:
        """
        try:
            pos = mt5.positions_get(group="*")
            sorted_tuple = sorted(pos, key=lambda x: x.time, reverse=True)
            try:
                for h in range(0, len(sorted_tuple)):
                    exist = False
                    for i in range(self.ui.pos_tree.topLevelItemCount()):
                        item = self.ui.pos_tree.topLevelItem(i)
                        if str(item.text(1)) == str(sorted_tuple[h].ticket):
                            exist = True
                            item.setText(3, str(sorted_tuple[h].volume))
                            item.setText(4, str(round(sorted_tuple[h].profit, 2)))
                            if sorted_tuple[h].profit > 0:
                                item.setForeground(4, QBrush(QColor("green")))
                            elif sorted_tuple[h].profit < 0:
                                item.setForeground(4, QBrush(QColor("red")))
                            else:
                                item.setForeground(4, QBrush(QColor("black")))

                    if not exist:
                        item = QTreeWidgetItem()
                        item.setText(4, str(round(sorted_tuple[h].profit, 2)))  # profit
                        item.setText(3, str(sorted_tuple[h].volume))  # volume

                        item.setText(1, str(sorted_tuple[h].ticket))
                        item.setText(0, str(sorted_tuple[h].symbol))
                        if sorted_tuple[h].type == 1:
                            item.setText(2, str("Sell"))
                            icon = QIcon()
                            icon.addFile(r"img/sell.png", QSize(8, 13), QIcon.Mode.Normal, QIcon.State.Off)
                            item.setIcon(0, icon)
                        else:
                            item.setText(2, str("Buy"))
                            icon = QIcon()
                            icon.addFile(r"img/buy.png", QSize(8, 13), QIcon.Mode.Normal, QIcon.State.Off)
                            item.setIcon(0, icon)
                        self.ui.pos_tree.addTopLevelItem(item)
                        if sorted_tuple[h].profit > 0:
                            item.setForeground(4, QBrush(QColor("green")))
                        elif sorted_tuple[h].profit < 0:
                            item.setForeground(4, QBrush(QColor("red")))
                        else:
                            item.setForeground(4, QBrush(QColor("black")))
            except Exception as error:
                print(error)
            try:
                for x in range(self.ui.pos_tree.topLevelItemCount()):
                    item = self.ui.pos_tree.topLevelItem(x)
                    exist = False
                    for i in range(0, len(sorted_tuple)):
                        if str(item.text(1)) == str(sorted_tuple[i].ticket):
                            exist = True
                    if not exist:
                        self.ui.pos_tree.takeTopLevelItem(x)
                        self.ui.pos_tree.clearSelection()
                        self.ticket_current_symbol = 0
            except Exception as error:
                print(error)
        except Exception as error:
            print(error)

    def RR1_chk(self):
        """
        check for rr1
        :return:
        """
        if self.ui.RR1.isChecked():
            self.rr1_timer.start()
        else:
            self.rr1_timer.stop()

    def RR2_chk(self):
        """
        check for rr2
        :return:
        """
        if self.ui.RR2.isChecked():
            self.rr2_timer.start()
        else:
            self.rr2_timer.stop()

    def trade_close(self, percentage, ticket, side, volume, comment, symbol):
        """
        close trade
        :param percentage:
        :param ticket:
        :param side:
        :param volume:
        :param comment:
        :param symbol:
        :return:
        """
        try:
            ask = mt5.symbol_info_tick(symbol).ask
            bid = mt5.symbol_info_tick(symbol).bid
            price = bid if side == 'buy' else ask
            type_t = self.mt5.ORDER_TYPE_SELL if side == 'buy' else self.mt5.ORDER_TYPE_BUY
            lot = round(volume * percentage / 100, 2)
            if 0.01 <= lot < volume:
                request = {
                    "action": self.mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "position": ticket,
                    "volume": lot,
                    'price': price,
                    "type": type_t,
                    "magic": self.magic,
                    "comment": comment,
                    "type_time": self.mt5.ORDER_TIME_GTC,
                }
                self.t1 = mt5.order_send(request)
                self.ui.lasterror_l.setHtml(comment + " " + self.ret[f'{self.t1.retcode}'])
                return self.t1.retcode
            else:
                self.ui.lasterror_l.setHtml(comment + " Lot is under 0.01 or Bigger than Position Lot")
                return "error"
        except Exception as errr:
            self.ui.lasterror_l.setHtml("Error On : " + comment + f" : {errr}")

    def RR1(self):
        """
        rr1 action
        :return:
        """
        positions = self.mt5.positions_get(group='*')
        det = self.mt5.account_info()._asdict()
        prf = float(det['balance']) * float(self.ui.RR_profitpct_1.text()) / 100
        for rr in range(0, len(positions)):
            if str(positions[rr].ticket) not in self.RRs['RR1'] and positions[rr].profit > prf:
                side = 'buy' if positions[rr].type == 0 else 'sell'
                chk = self.trade_close(float(self.ui.RR_closepct_1.text()), positions[rr].ticket, side,
                                       positions[rr].volume, f"RR1 {positions[rr].symbol}: ", positions[rr].symbol)
                if chk == 10009:
                    self.RRs['RR1'][str(positions[rr].ticket)] = positions[rr].symbol
                elif chk == 'error':
                    self.RRs['RR1'][str(positions[rr].ticket)] = positions[rr].symbol

    def RR2(self):
        """
        rr2 action
        :return:
        """
        positions = self.mt5.positions_get(group='*')
        det = self.mt5.account_info()._asdict()
        prf = float(det['balance']) * float(self.ui.RR_profitpct_2.text()) / 100
        for rr in range(0, len(positions)):
            if str(positions[rr].ticket) not in self.RRs['RR2'] and positions[rr].profit >= prf:
                side = 'buy' if positions[rr].type == 0 else 'sell'
                chk = self.trade_close(float(self.ui.RR_closepct_2.text()), positions[rr].ticket, side,
                                       positions[rr].volume, f"RR2 {positions[rr].symbol}: ", positions[rr].symbol)
                if chk == 10009:
                    self.RRs['RR2'][str(positions[rr].ticket)] = positions[rr].symbol
                elif chk == 'error':
                    self.RRs['RR2'][str(positions[rr].ticket)] = positions[rr].symbol

    def chk(self):
        """
        check for sl
        :return:
        """
        if self.ui.show_chart_ch.isChecked():
            self.set_sl = True
            self.min_sl_buff = self.ui.minsl_t.text()
            self.ui.minsl_t.setEnabled(False)
        else:
            self.set_sl = False
            self.ui.minsl_t.setText(self.min_sl_buff)
            self.ui.minsl_t.setEnabled(True)

    def chart_updater(self):
        """update chart"""
        rates = self.mt5.copy_rates_from_pos(self.symbol, self.mt5.TIMEFRAME_M1, 0, 40)
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        rnd = int(self.mt5.symbol_info(self.symbol).digits)
        mx = df['high'].max() + (10 / (pow(10, rnd)))
        mn = df['low'].min() - (10 / (pow(10, rnd)))
        lln = len(df)
        df['date'] = df.index
        df = df[['date', 'open', 'close', 'low', 'high']].to_numpy()
        self.square.setData([0, 0, lln, lln, 0], [mn, mx, mx, mn, mn], pen=mkPen(color=(255, 0, 0, 1), width=2))

        self.plot_widget.setYRange(mn, mx)
        self.plot_widget.removeItem(self.candle)
        self.candle = CandlestickItem(df)
        self.plot_widget.addItem(self.candle)

    def on_mouse_click_chart(self, event):
        """
        set sl on chart
        :param event:
        :return:
        """
        mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(event.scenePos())
        if self.square.contains(mouse_point):
            self.line.setVisible(True)
            self.line.setPos(mouse_point.y())
            if self.set_sl:
                rnd = int(self.mt5.symbol_info(self.symbol).digits)
                self.ui.minsl_t.setText(str(round(self.line.getPos()[1], int(rnd))))
        else:
            self.line.setVisible(False)

    def show_calendar(self):
        """
        show calendar
        :return:
        """
        self.ui.table_frame.show()
        self.ui.show_chart_b.show()
        self.ui.chart_frame.hide()
        self.ui.show_calendar_b.hide()
        self.chart_updater_timer.stop()

    def show_chart(self):
        """
        show chart
        :return:
        """
        self.ui.show_statement_b.setText("Statement")
        self.ui.table_frame.hide()
        self.ui.show_chart_b.hide()
        self.ui.chart_frame.show()
        self.ui.show_calendar_b.show()
        if self.mt5.last_error()[1] != 'No IPC connection' and self.mt5.last_error()[1] != '':
            if self.layout.itemAt(0).widget() != self.plot_widget:
                self.layout.itemAt(0).widget().hide()
                self.layout.replaceWidget(self.layout.itemAt(0).widget(), self.plot_widget)
            rates = self.mt5.copy_rates_from_pos(self.symbol, self.mt5.TIMEFRAME_M1, 0, 40)
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            rnd = int(self.mt5.symbol_info(self.symbol).digits)
            mx = df['high'].max() + (10 / (pow(10, rnd)))
            mn = df['low'].min() - (10 / (pow(10, rnd)))
            lln = len(df)
            df['date'] = df.index
            df = df[['date', 'open', 'close', 'low', 'high']].to_numpy()
            try:
                self.plot_widget.removeItem(self.candle)

            except Exception as error:
                print(error)
            try:
                self.plot_widget.removeItem(self.line)
            except Exception as error:
                print(error)
            try:
                self.plot_widget.removeItem(self.square)
            except Exception as error:
                print(error)
            self.plot_widget.setYRange(mn, mx)
            self.square = PlotCurveItem([0, 0, lln, lln, 0], [mn, mx, mx, mn, mn],
                                        pen=mkPen(color=(255, 0, 0, 1), width=2))
            self.plot_widget.addItem(self.square)
            self.candle = CandlestickItem(df)
            self.plot_widget.addItem(self.candle)
            # Create a line item that will be drawn on the y-axis when the user clicks on the square
            self.line = InfiniteLine(angle=0, movable=False, pen=mkPen(color=(0, 255, 0), width=2))
            self.line.setVisible(False)
            self.plot_widget.addItem(self.line)
            self.chart_updater_timer.start()
        else:

            self.pixmap_imgs.load("img/dissconnect.png")
            pixmap = self.pixmap_imgs.scaled(QSize(421, 141), Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation)
            self.lbl.setPixmap(pixmap)
            self.lbl.show()
            self.layout.replaceWidget(self.layout.itemAt(0).widget(), self.lbl)
            self.ui.show_chart_f.setLayout(self.layout)

    def set_img(self):
        """telegram image"""
        try:
            pixmap = QPixmap("img/default_avatar.png")

            # Scale the pixmap to 60*60 and keep the aspect ratio
            pixmap = pixmap.scaled(QSize(70, 70), Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)

            self.ui.avatar_image.setPixmap(pixmap)
            # Define the token and the user id
            token = ""
            user_id = self.userid
            parame = {
                'user_id': user_id,
            }
            # Get the user profile photos
            photos = requests.post(f"https://api.telegram.org/bot{token}/getUserProfilePhotos", params=parame)
            if photos.status_code == 200:
                photos = photos.json()
                # Get the file id of the first photo
                file_id = photos["result"]["photos"][0][0]["file_id"]
                #
                # # Get the file information
                file = requests.get(f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}").json()
                #
                # # Get the file path
                file_path = file["result"]["file_path"]
                #
                # # Get the file url
                file_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
                #
                # # Download the file
                file_data = requests.get(file_url).content
                #
                # # Save the file
                with open("avatar.jpg", "wb") as f:
                    f.write(file_data)

                pixmap = QPixmap("avatar.jpg")

                # Scale the pixmap to 60*60 and keep the aspect ratio
                pixmap = pixmap.scaled(QSize(70, 70), Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)

                self.ui.avatar_image.setPixmap(pixmap)
            else:
                print('Cant Catch Telegram')
            parame = {
                'chat_id': user_id,
            }

            # Get the user profile photos
            photos = requests.post(f"https://api.telegram.org/bot{token}/getChat", params=parame)
            if photos.status_code == 200:
                photos = photos.json()
                self.ui.telegramname_l.setText(photos['result']['first_name'])
            else:
                print('Cant Catch Telegram')
                # self.ui.lasterror_l.setHtml(f'Error Getting Personal Name : {photos.status_code}')
        except requests.ConnectionError:
            print("error Telegram")
        except requests.RequestException as e:
            print("error Telegram")
        except Exception as errorimg:
            print("error Telegram")

    def localize_time(self, time_o):
        """
        localize time
        :param time_o:
        :return:
        """
        my_time = time_o
        if 'All Day' not in time_o:
            if 'am' in time_o or 'pm' in time_o:
                time_obj = datetime.strptime(my_time, "%I:%M%p")

                # Format the time using strftime with the format "%H:%M"
                # %H is the hour in 24-hour format
                time_24 = time_obj.strftime("%H:%M")
            else:
                time_24 = time_o
            tt = datetime.strptime(time_24, "%H:%M")

            tt = tt - timedelta(hours=3.5)

            offset = time.timezone if (time.localtime().tm_isdst == 0) else time.altzone
            offset = offset / 60 / 60 * -1
            yourtime = tt + timedelta(hours=offset)
            yourtime = yourtime.time().strftime("%H:%M")
            return yourtime
        else:
            return time_o

    def calendar(self):
        """
        calendar
        :return:
        """
        try:
            while True:
                try:
                    url = ""
                    try:
                        response = requests.get(url)
                    except Exception as trrr:
                        self.calendar_e = False
                        return False
                    self.ui.calendar_table.setRowCount(0)
                    if response.status_code == 200:
                        df = pd.read_csv(io.StringIO(response.text), header=0,
                                         usecols=['Time', "Country", "Impact", "Title", 'up'])
                        cnt = 0
                        for cl in range(0, len(df)):
                            if "High" in df['Impact'].iloc[cl]:
                                # if df['Country'].iloc[cl] in self.symbol:
                                cnt += 1
                                ro = self.ui.calendar_table.rowCount()
                                self.ui.calendar_table.insertRow(ro)
                                c_timee = self.localize_time(df['Time'].iloc[cl])
                                aa = QTableWidgetItem(str(c_timee))
                                nnn = datetime.now().strptime(datetime.now().strftime("%H:%M"), "%H:%M")
                                if "All Day" != str(c_timee) not in self.time_news and \
                                        df['Country'].iloc[cl] in self.symbol.upper():
                                    if datetime.strptime(c_timee, "%H:%M") > nnn >= \
                                            datetime.strptime(c_timee, "%H:%M") - timedelta(minutes=10):
                                        self.sound = 'news'
                                        self.time_news.append(str(c_timee))
                                aa.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                                self.ui.calendar_table.setItem(ro, 0, aa)
                                aa = QTableWidgetItem(str(df['Country'].iloc[cl]))
                                aa.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                                self.ui.calendar_table.setItem(ro, 1, aa)
                                aa = QTableWidgetItem(str(df['Impact'].iloc[cl]))
                                aa.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                                self.ui.calendar_table.setItem(ro, 2, aa)
                                aa = QTableWidgetItem(str(df['Title'].iloc[cl]))
                                aa.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                                self.ui.calendar_table.setItem(ro, 3, aa)
                                aa = QTableWidgetItem(str(self.localize_time(df['up'].iloc[cl])))
                                aa.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                                self.ui.calendar_table.setItem(ro, 4, aa)

                        if cnt == 0 and len(df) >= 1 and response.status_code == 200:
                            txt = "We Haven't Important News For Today ( "
                            for iss in range(0, len(df)):
                                txt += df['Country'].iloc[iss] + " | "
                            txt += ")"
                            self.ui.nownews_l.setText(txt)
                            # self.resize(521, 427)
                            self.ui.nownews_l.show()
                            # self.ui.calendar_table.hide()
                    else:
                        self.ui.nownews_l.setText(f"Error On Getting News Code : {response.status_code}")
                        self.ui.nownews_l.setStyleSheet('color: rgb(255, 0, 127);')
                        # self.resize(521, 427)
                        self.ui.nownews_l.show()
                        # self.ui.calendar_table.hide()
                        # Window.resize(521,400)
                    time.sleep(60)
                except Exception as erc:
                    print(erc)

        except Exception as erc:
            print(erc)

    def closeall(self):
        """
        close all
        :return:
        """
        try:
            if self.ticket_current_symbol == 0:
                positions = self.mt5.positions_get(symbol=self.symbol)
                if len(positions) >= 0:
                    for i in range(0, len(positions)):
                        if positions[i].type == 0:
                            price = mt5.symbol_info_tick(self.symbol).ask
                            request = {
                                "action": self.mt5.TRADE_ACTION_DEAL,
                                "symbol": self.symbol,
                                "position": positions[i].ticket,
                                "volume": positions[i].volume,
                                'price': price,
                                "type": self.mt5.ORDER_TYPE_SELL,
                                "magic": self.magic,
                                "comment": "Close1",
                                "type_time": self.mt5.ORDER_TIME_GTC,
                            }
                            self.t1 = mt5.order_send(request)
                            self.ui.lasterror_l.setHtml(self.ret[f'{self.t1.retcode}'])
                        else:
                            price = mt5.symbol_info_tick(self.symbol).bid
                            request = {
                                "action": self.mt5.TRADE_ACTION_DEAL,
                                "symbol": self.symbol,
                                "position": positions[i].ticket,
                                "volume": positions[i].volume,
                                'price': price,
                                "type": self.mt5.ORDER_TYPE_BUY,
                                "comment": "Close1",
                                "magic": self.magic,
                                "type_time": self.mt5.ORDER_TIME_GTC,
                            }
                            self.t1 = mt5.order_send(request)
                            self.ui.lasterror_l.setHtml(self.ret[f'{self.t1.retcode}'])
            else:
                positions = self.mt5.positions_get(group="*")
                if len(positions) >= 0:
                    for i in range(0, len(positions)):
                        if self.ticket_current_symbol == positions[i].ticket:
                            if positions[i].type == 0:
                                price = mt5.symbol_info_tick(positions[i].symbol).ask
                                request = {
                                    "action": self.mt5.TRADE_ACTION_DEAL,
                                    "symbol": positions[i].symbol,
                                    "position": positions[i].ticket,
                                    "volume": positions[i].volume,
                                    'price': price,
                                    "type": self.mt5.ORDER_TYPE_SELL,
                                    "magic": self.magic,
                                    "comment": "Close1",
                                    "type_time": self.mt5.ORDER_TIME_GTC,
                                }
                                self.t1 = mt5.order_send(request)
                                self.ui.lasterror_l.setHtml(self.ret[f'{self.t1.retcode}'])
                            else:
                                price = mt5.symbol_info_tick(positions[i].symbol).bid
                                request = {
                                    "action": self.mt5.TRADE_ACTION_DEAL,
                                    "symbol": positions[i].symbol,
                                    "position": positions[i].ticket,
                                    "volume": positions[i].volume,
                                    'price': price,
                                    "type": self.mt5.ORDER_TYPE_BUY,
                                    "comment": "Close1",
                                    "magic": self.magic,
                                    "type_time": self.mt5.ORDER_TIME_GTC,
                                }
                                self.t1 = mt5.order_send(request)
                                self.ui.lasterror_l.setHtml(self.ret[f'{self.t1.retcode}'])
                            break
                self.clear_tree_selection()
        except Exception as error:
            self.ui.lasterror_l.setHtml(str(error))

    def closepct2(self):
        """
        close percentage 2
        :return:
        """
        try:
            if self.ticket_current_symbol == 0:
                positions = self.mt5.positions_get(symbol=self.symbol)
                if len(positions) >= 0:
                    pct = float(self.ui.close2_t.text())
                    for i in range(0, len(positions)):
                        if 0.01 <= positions[i].volume * pct / 100 < positions[i].volume > 0.01:
                            if positions[i].type == 0:
                                price = mt5.symbol_info_tick(self.symbol).ask
                                request = {
                                    "action": self.mt5.TRADE_ACTION_DEAL,
                                    "symbol": self.symbol,
                                    "position": positions[i].ticket,
                                    "volume": round(positions[i].volume * pct / 100, 2),
                                    'price': price,
                                    "type": self.mt5.ORDER_TYPE_SELL,
                                    "comment": "Close2",
                                    "magic": self.magic,
                                    "type_time": self.mt5.ORDER_TIME_GTC,
                                }
                                self.t1 = mt5.order_send(request)
                                self.ui.lasterror_l.setHtml(self.ret[f'{self.t1.retcode}'])
                            else:
                                price = mt5.symbol_info_tick(self.symbol).bid
                                request = {
                                    "action": self.mt5.TRADE_ACTION_DEAL,
                                    "symbol": self.symbol,
                                    "position": positions[i].ticket,
                                    "volume": round(positions[i].volume * pct / 100, 2),
                                    'price': price,
                                    "type": self.mt5.ORDER_TYPE_BUY,
                                    "comment": "Close2",
                                    "magic": self.magic,
                                    "type_time": self.mt5.ORDER_TIME_GTC,
                                }
                                self.t1 = mt5.order_send(request)
                                self.ui.lasterror_l.setHtml(self.ret[f'{self.t1.retcode}'])
                        else:
                            self.ui.lasterror_l.setHtml(f'Cant Partial ({positions[i].volume * pct / 100})')
            else:
                positions = self.mt5.positions_get(group="*")
                if len(positions) >= 0:
                    pct = float(self.ui.close2_t.text())
                    for i in range(0, len(positions)):
                        if self.ticket_current_symbol == positions[i].ticket:
                            if 0.01 <= positions[i].volume * pct / 100 < positions[i].volume > 0.01:
                                if positions[i].type == 0:
                                    price = mt5.symbol_info_tick(positions[i].symbol).ask
                                    request = {
                                        "action": self.mt5.TRADE_ACTION_DEAL,
                                        "symbol": positions[i].symbol,
                                        "position": positions[i].ticket,
                                        "volume": round(positions[i].volume * pct / 100, 2),
                                        'price': price,
                                        "type": self.mt5.ORDER_TYPE_SELL,
                                        "comment": "Close2",
                                        "magic": self.magic,
                                        "type_time": self.mt5.ORDER_TIME_GTC,
                                    }
                                    self.t1 = mt5.order_send(request)
                                    self.ui.lasterror_l.setHtml(self.ret[f'{self.t1.retcode}'])
                                else:
                                    price = mt5.symbol_info_tick(positions[i].symbol).bid
                                    request = {
                                        "action": self.mt5.TRADE_ACTION_DEAL,
                                        "symbol": positions[i].symbol,
                                        "position": positions[i].ticket,
                                        "volume": round(positions[i].volume * pct / 100, 2),
                                        'price': price,
                                        "type": self.mt5.ORDER_TYPE_BUY,
                                        "comment": "Close2",
                                        "magic": self.magic,
                                        "type_time": self.mt5.ORDER_TIME_GTC,
                                    }
                                    self.t1 = mt5.order_send(request)
                                    self.ui.lasterror_l.setHtml(self.ret[f'{self.t1.retcode}'])
                            else:
                                self.ui.lasterror_l.setHtml(f'Cant Partial ({positions[i].volume * pct / 100})')
                            break
                    self.clear_tree_selection()
        except Exception as error:
            self.ui.lasterror_l.setHtml(str(error))

    def closepct(self):
        """
        close percentage 1
        :return:
        """
        try:
            if self.ticket_current_symbol == 0:
                positions = self.mt5.positions_get(symbol=self.symbol)
                if len(positions) >= 0:
                    pct = float(self.ui.close1_t.text())
                    for i in range(0, len(positions)):
                        if 0.01 <= positions[i].volume * pct / 100 < positions[i].volume > 0.01:
                            if positions[i].type == 0:
                                price = mt5.symbol_info_tick(self.symbol).ask
                                request = {
                                    "action": self.mt5.TRADE_ACTION_DEAL,
                                    "symbol": self.symbol,
                                    "position": positions[i].ticket,
                                    "volume": round(positions[i].volume * pct / 100, 2),
                                    'price': price,
                                    "type": self.mt5.ORDER_TYPE_SELL,
                                    "comment": "Close1",
                                    "magic": self.magic,
                                    "type_time": self.mt5.ORDER_TIME_GTC,
                                }
                                self.t1 = mt5.order_send(request)
                                self.ui.lasterror_l.setHtml(self.ret[f'{self.t1.retcode}'])
                            else:
                                price = mt5.symbol_info_tick(self.symbol).bid
                                request = {
                                    "action": self.mt5.TRADE_ACTION_DEAL,
                                    "symbol": self.symbol,
                                    "position": positions[i].ticket,
                                    "volume": round(positions[i].volume * pct / 100, 2),
                                    'price': price,
                                    "type": self.mt5.ORDER_TYPE_BUY,
                                    "comment": "Close1",
                                    "magic": self.magic,
                                    "type_time": self.mt5.ORDER_TIME_GTC,
                                }
                                self.t1 = mt5.order_send(request)
                                self.ui.lasterror_l.setHtml(self.ret[f'{self.t1.retcode}'])
                        else:
                            self.ui.lasterror_l.setHtml(f'Cant Partial ({positions[i].volume * pct / 100})')

            else:
                positions = self.mt5.positions_get(group="*")
                if len(positions) >= 0:
                    pct = float(self.ui.close1_t.text())
                    for i in range(0, len(positions)):
                        if self.ticket_current_symbol == positions[i].ticket:
                            if 0.01 <= positions[i].volume * pct / 100 < positions[i].volume > 0.01:
                                if positions[i].type == 0:
                                    price = mt5.symbol_info_tick(positions[i].symbol).ask
                                    request = {
                                        "action": self.mt5.TRADE_ACTION_DEAL,
                                        "symbol": positions[i].symbol,
                                        "position": positions[i].ticket,
                                        "volume": round(positions[i].volume * pct / 100, 2),
                                        'price': price,
                                        "type": self.mt5.ORDER_TYPE_SELL,
                                        "comment": "Close1",
                                        "magic": self.magic,
                                        "type_time": self.mt5.ORDER_TIME_GTC,
                                    }
                                    self.t1 = mt5.order_send(request)
                                    self.ui.lasterror_l.setHtml(self.ret[f'{self.t1.retcode}'])
                                else:
                                    price = mt5.symbol_info_tick(positions[i].symbol).bid
                                    request = {
                                        "action": self.mt5.TRADE_ACTION_DEAL,
                                        "symbol": positions[i].symbol,
                                        "position": positions[i].ticket,
                                        "volume": round(positions[i].volume * pct / 100, 2),
                                        'price': price,
                                        "type": self.mt5.ORDER_TYPE_BUY,
                                        "comment": "Close1",
                                        "magic": self.magic,
                                        "type_time": self.mt5.ORDER_TIME_GTC,
                                    }
                                    self.t1 = mt5.order_send(request)
                                    self.ui.lasterror_l.setHtml(self.ret[f'{self.t1.retcode}'])

                            else:
                                self.ui.lasterror_l.setHtml(f'Cant Partial ({positions[i].volume * pct / 100})')
                            break
                    self.clear_tree_selection()
        except Exception as error:
            self.ui.lasterror_l.setHtml(str(error))

    def freerisk(self):
        """
        free risk
        :return:
        """
        try:
            if self.ticket_current_symbol == 0:
                positions = self.mt5.positions_get(symbol=self.symbol)
                rnd = int(self.mt5.symbol_info(self.symbol).digits)
                if len(positions) >= 0:
                    for i in range(0, len(positions)):
                        request = {
                            "action": self.mt5.TRADE_ACTION_SLTP,
                            "symbol": self.symbol,
                            "position": positions[i].ticket,
                            "sl": round(positions[i].price_open, rnd),
                            "comment": "Free Risk",
                            "magic": self.magic,
                            "type_time": self.mt5.ORDER_TIME_GTC,
                        }
                        self.t1 = self.mt5.order_send(request)
                        self.ui.lasterror_l.setHtml(self.ret[f'{self.t1.retcode}'])
            else:
                positions = self.mt5.positions_get(group="*")

                if len(positions) >= 0:
                    for i in range(0, len(positions)):
                        if positions[i].ticket == self.ticket_current_symbol:
                            rnd = int(self.mt5.symbol_info(positions[i].symbol).digits)
                            request = {
                                "action": self.mt5.TRADE_ACTION_SLTP,
                                "symbol": positions[i].symbol,
                                "position": positions[i].ticket,
                                "sl": round(positions[i].price_open, rnd),
                                "comment": "Free Risk",
                                "magic": self.magic,
                                "type_time": self.mt5.ORDER_TIME_GTC,
                            }
                            self.t1 = self.mt5.order_send(request)
                            self.ui.lasterror_l.setHtml(self.ret[f'{self.t1.retcode}'])
                            break
                self.clear_tree_selection()
        except Exception as error:
            self.ui.lasterror_l.setHtml(str(error))

    def trade_act(self, fixed_lot, sl, risk, side, comment, devide):
        """
        trade action
        :param fixed_lot:
        :param sl:
        :param risk:
        :param side:
        :param comment:
        :param devide:
        :return:
        """
        det = self.mt5.account_info()._asdict()
        balance = float(det['balance'])
        rnd = int(self.mt5.symbol_info(self.symbol).digits)
        if fixed_lot == 0:
            if sl == 0:
                self.ui.lasterror_l.setHtml(comment + " " + f'Set Stop Loss')
            else:
                if risk != 0:
                    price = self.mt5.symbol_info_tick(self.symbol).ask if side == 'buy' else \
                        self.mt5.symbol_info_tick(self.symbol).bid
                    stt = sl if not self.set_sl else abs(float(self.ui.minsl_t.text()) - price) * \
                                                     int(self.mt5.symbol_info(self.symbol).trade_contract_size)
                    lot = ((balance * risk) / 100 / stt) / devide
                    if lot >= 0.01:
                        type_t = self.mt5.ORDER_TYPE_BUY if side == "buy" else self.mt5.ORDER_TYPE_SELL
                        stop_buy = round(price - (sl / (pow(10, rnd))), rnd)
                        stop_sell = round(price + (sl / (pow(10, rnd))), rnd)
                        stoploss_ch = stop_buy if side == 'buy' else stop_sell
                        stoploss = stoploss_ch if not self.set_sl else round(float(self.ui.minsl_t.text()), rnd)
                        request = {
                            "action": self.mt5.TRADE_ACTION_DEAL,
                            "symbol": self.symbol,
                            "volume": round(lot, 2),
                            'price': price,
                            'sl': stoploss,
                            "type": type_t,
                            "magic": self.magic,
                            "type_time": self.mt5.ORDER_TIME_GTC,
                        }
                        self.t1 = self.mt5.order_send(request)
                        self.ui.lasterror_l.setHtml(comment + " " + self.ret[f'{self.t1.retcode}'])
                    else:
                        self.ui.lasterror_l.setHtml(comment + " " + f'Lot Size is Lower Than 0.01')
                else:
                    self.ui.lasterror_l.setHtml(comment + " " + f'Set Risk Percentage')
        else:
            if sl == 0:
                self.ui.lasterror_l.setHtml(comment + " " + f'Set Stop Loss')
            else:
                if fixed_lot / devide >= 0.01:
                    type_t = self.mt5.ORDER_TYPE_BUY if side == "buy" else self.mt5.ORDER_TYPE_SELL
                    price = self.mt5.symbol_info_tick(self.symbol).ask if side == 'buy' else \
                        self.mt5.symbol_info_tick(self.symbol).bid
                    stop_buy = round(price - (sl / (pow(10, rnd))), rnd)
                    stop_sell = round(price + (sl / (pow(10, rnd))), rnd)
                    stoploss_ch = stop_buy if side == 'buy' else stop_sell
                    stoploss = stoploss_ch if not self.set_sl else round(float(self.ui.minsl_t.text()), rnd)
                    request = {
                        "action": self.mt5.TRADE_ACTION_DEAL,
                        "symbol": self.symbol,
                        "volume": round(fixed_lot / devide, 2),
                        'price': price,
                        'sl': stoploss,
                        "type": type_t,
                        "magic": self.magic,
                        "type_time": self.mt5.ORDER_TIME_GTC,
                    }
                    self.t1 = self.mt5.order_send(request)
                    self.ui.lasterror_l.setHtml(comment + " " + self.ret[f'{self.t1.retcode}'])
                else:
                    self.ui.lasterror_l.setHtml(comment + " " + f'Lot Size is Lower Than 0.01')
        self.clear_tree_selection()

    def buy(self):
        """
        Buy
        :return:
        """
        try:
            self.trade_act(float(self.ui.fixedlot_t.text()), float(self.ui.minsl_t.text()),
                           float(self.ui.riskperc_t.text()), 'buy', "Buy", 1)
            self.click_sound.play()
            if self.mt5.account_info().margin_mode == 0:
                self.RRs = {k: v for k, v in self.RRs.items() if not (v == self.symbol)}
        except Exception as erc:
            self.ui.lasterror_l.setHtml(str(erc))

    def halfbuy(self):
        """
        Half Buy
        :return:
        """
        try:
            self.trade_act(float(self.ui.fixedlot_t.text()), float(self.ui.minsl_t.text()),
                           float(self.ui.riskperc_t.text()), 'buy', "Half Buy", 2)
            self.click_sound.play()
        except Exception as erc:
            self.ui.lasterror_l.setHtml(str(erc))

    def sell(self):
        """Sell"""
        try:
            self.trade_act(float(self.ui.fixedlot_t.text()), float(self.ui.minsl_t.text()),
                           float(self.ui.riskperc_t.text()), 'sell', "Sell", 1)
            self.click_sound.play()
            if self.mt5.account_info().margin_mode == 0:
                self.RRs = {k: v for k, v in self.RRs.items() if not (v == self.symbol)}
        except Exception as erc:
            self.ui.lasterror_l.setHtml(str(erc))

    def halfsell(self):
        """Half Sell"""
        try:
            self.trade_act(float(self.ui.fixedlot_t.text()), float(self.ui.minsl_t.text()),
                           float(self.ui.riskperc_t.text()), 'sell', "Half Sell", 2)
            self.click_sound.play()
        except Exception as erc:
            self.ui.lasterror_l.setHtml(str(erc))

    def save_info(self):
        """
        Save Setup
        :return:
        """
        ssl = self.ui.minsl_t.text() if self.min_sl_buff == "" else str(self.min_sl_buff)
        ss = {
            "mt5 path": self.ui.mt5terminalpath_t.text(),
            'userpassserver': self.ui.userpassserver_t.text(),
            'riskperc': self.ui.riskperc_t.text(),
            'close1': self.ui.close1_t.text(),
            'close2': self.ui.close2_t.text(),
            'fixedlot': self.ui.fixedlot_t.text(),
            'drawdown': self.ui.drawdown_t.text(),
            'minsl': ssl,
            'symbol': self.ui.symbol_t.text(),
            "RR1_profit_pct": self.ui.RR_profitpct_1.text(),
            "RR1_close_pct": self.ui.RR_closepct_1.text(),
            "RR2_profit_pct": self.ui.RR_profitpct_2.text(),
            "RR2_close_pct": self.ui.RR_closepct_2.text(),
        }
        file_name, _ = QFileDialog.getSaveFileName(None, "Save File", "", "JSON Files (*.json)")
        if file_name:
            with open(file_name, "w") as f:
                json.dump(ss, f)

    def load_info(self):
        """
        Load Setup
        :return:
        """
        file_name, _ = QFileDialog.getOpenFileName(None, "Load File", "", "JSON Files (*.json)")
        if file_name:
            with open(file_name, 'r') as f:
                sd = json.load(f)
                self.ui.mt5terminalpath_t.setText(sd['mt5 path'])
                self.ui.userpassserver_t.setText(sd['userpassserver'])
                self.ui.riskperc_t.setText(sd['riskperc'])
                self.ui.close1_t.setText(sd['close1'])
                self.ui.close2_t.setText(sd['close2'])
                self.ui.fixedlot_t.setValue(float(sd['fixedlot']))
                self.ui.drawdown_t.setText(sd['drawdown'])
                self.ui.minsl_t.setText(sd['minsl'])
                self.ui.symbol_t.setText(sd['symbol'])
                self.ui.RR_profitpct_1.setText(sd['RR1_profit_pct'])
                self.ui.RR_closepct_1.setText(sd['RR1_close_pct'])
                self.ui.RR_profitpct_2.setText(sd['RR2_profit_pct'])
                self.ui.RR_closepct_2.setText(sd['RR2_close_pct'])

    def set_flag(self, situ):
        """
        check for start of day
        :param situ:
        :return:
        """
        try:
            file_path = Path('accounts.json')
            det = self.mt5.account_info()._asdict()
            with file_path.open("r") as f:
                data = json.load(f)
                data[f'{det["login"]}']['date'] = datetime.now().strftime('%d/%m/%Y')
                data[f'{det["login"]}']['flag'] = situ
                self.start_balance = str(data[f'{det["login"]}']['balance'])
                with open('accounts.json', 'w') as dd:
                    json.dump(data, dd)
        except Exception as err:
            self.ui.lasterror_l.setHtml(str(err))

    def flag_do(self, flag):
        """Check For Draw Down"""
        if flag == 'drawdown':
            self.trade = False
            self.set_flag('drawdown')
            self.ui.lasterror_l.setHtml("You Reached Maximum DrawDown, Trading is Disabled")
            self.ui.drawdown_t.setEnabled(False)
            self.ui.buy.setEnabled(False)
            self.ui.sell.setEnabled(False)
            self.ui.halfbuy.setEnabled(False)
            self.ui.halfsell.setEnabled(False)
            self.prof.stop()
            positions = self.mt5.positions_get(group="*")
            if len(positions) >= 0:
                for i in range(0, len(positions)):
                    if positions[i].type == 0:
                        price = mt5.symbol_info_tick(positions[i].symbol).ask
                        request = {
                            "action": self.mt5.TRADE_ACTION_DEAL,
                            "symbol": positions[i].symbol,
                            "position": positions[i].ticket,
                            "volume": positions[i].volume,
                            'price': price,
                            "type": self.mt5.ORDER_TYPE_SELL,
                            "magic": self.magic,
                            "comment": "DD",
                            "type_time": self.mt5.ORDER_TIME_GTC,
                        }
                        self.t1 = mt5.order_send(request)
                        self.ui.lasterror_l.setHtml(self.ret[f'{self.t1.retcode}'])
                    else:
                        price = mt5.symbol_info_tick(positions[i].symbol).bid
                        request = {
                            "action": self.mt5.TRADE_ACTION_DEAL,
                            "symbol": positions[i].symbol,
                            "position": positions[i].ticket,
                            "volume": positions[i].volume,
                            'price': price,
                            "type": self.mt5.ORDER_TYPE_BUY,
                            "comment": "DD",
                            "magic": self.magic,
                            "type_time": self.mt5.ORDER_TIME_GTC,
                        }
                        self.t1 = mt5.order_send(request)
                        self.ui.lasterror_l.setHtml(self.ret[f'{self.t1.retcode}'])
        elif flag == 'set_drawdown':
            file_path = Path(r'accounts.json')
            det = self.mt5.account_info()._asdict()
            with file_path.open("r") as f:
                data = json.load(f)
            data[f'{det["login"]}']['drawdown'] = self.ui.drawdown_t.text()
            with open(r'accounts.json', 'w') as dd:
                json.dump(data, dd)
            self.ui.drawdown_t.setEnabled(False)

    def balance_set(self):
        """Set Balance For Start of Day"""
        try:
            file_path = Path(r'accounts.json')
            det = self.mt5.account_info()._asdict()
            if file_path.is_file() or file_path.exists():
                with file_path.open("r") as f:
                    data = json.load(f)
                    if str(det['login']) in data:
                        if data[f'{det["login"]}']['date'] == datetime.now().strftime('%d/%m/%Y'):
                            self.start_balance = str(data[f'{det["login"]}']['balance'])
                            if data[f'{det["login"]}']['flag'] == 'drawdown':
                                self.flag_do('drawdown')
                            if 'drawdown' in data[f'{det["login"]}']:
                                self.ui.drawdown_t.setText(str(data[f'{det["login"]}']['drawdown']))
                                self.ui.drawdown_t.setEnabled(False)
                            else:
                                self.flag_do('set_drawdown')
                        else:
                            data[f'{det["login"]}'] = {}
                            data[f'{det["login"]}']['date'] = datetime.now().strftime('%d/%m/%Y')
                            data[f'{det["login"]}']['balance'] = det['balance']
                            data[f'{det["login"]}']['flag'] = 'ready'
                            self.start_balance = str(data[f'{det["login"]}']['balance'])
                            with open(r'accounts.json', 'w') as dd:
                                json.dump(data, dd)
                            self.flag_do('set_drawdown')
                    else:
                        data[f'{det["login"]}'] = {}
                        data[f'{det["login"]}']['date'] = datetime.now().strftime('%d/%m/%Y')
                        data[f'{det["login"]}']['balance'] = det['balance']
                        data[f'{det["login"]}']['flag'] = 'ready'
                        self.start_balance = str(data[f'{det["login"]}']['balance'])
                        with open(r'accounts.json', 'w') as dd:
                            json.dump(data, dd)
                        self.flag_do('set_drawdown')
            else:
                data = {}
                data[f'{det["login"]}'] = {}
                data[f'{det["login"]}']['date'] = datetime.now().strftime('%d/%m/%Y')
                data[f'{det["login"]}']['balance'] = det['balance']
                data[f'{det["login"]}']['flag'] = 'ready'
                self.start_balance = str(data[f'{det["login"]}']['balance'])
                with open(r'accounts.json', 'w') as dd:
                    json.dump(data, dd)
                self.flag_do('set_drawdown')
        except Exception as erc:
            self.ui.lasterror_l.setHtml(str(erc))

    def start(self):
        """
        Start and initialize
        :return:
        """
        try:
            if datetime.strptime(datetime.now().strftime('%d/%m/%Y'), "%d/%m/%Y") > datetime.strptime("29/02/2024",
                                                                                                      "%d/%m/%Y"):
                self.close()
            if self.ui.mt5terminalpath_t.text() != '' and self.ui.userpassserver_t.text() == '':
                if not self.mt5.initialize(path=self.ui.mt5terminalpath_t.text()):
                    pass
                self.ui.lasterror_l.setHtml(str(self.mt5.last_error()[1]))
                if self.mt5.last_error()[1] == "Success":
                    det = self.mt5.account_info()._asdict()
                    self.ui.username_l.setText(str(det['login']))
                    self.ui.server_l.setText(str(det['server']))
                    self.symbol = self.ui.symbol_t.text()
                    self.flag = True
                    self.balance_set()
                    self.pos_time.start()
                    # self.ui.drawdown_t.setEnabled(False)
            elif self.ui.mt5terminalpath_t.text() != '' and self.ui.userpassserver_t.text() != '':
                try:
                    wraper = self.ui.userpassserver_t.text().split(':')
                    if not self.mt5.initialize(path=self.ui.mt5terminalpath_t.text(),
                                               login=int(wraper[0]),
                                               password=str(wraper[1]),
                                               server=str(wraper[2])):
                        pass
                    self.ui.lasterror_l.setHtml(str(self.mt5.last_error()[1]))
                    if self.mt5.last_error()[1] == "Success":
                        det = self.mt5.account_info()._asdict()
                        self.ui.username_l.setText(str(det['login']))
                        self.ui.server_l.setText(str(det['server']))
                        self.symbol = self.ui.symbol_t.text()
                        self.flag = True
                        self.balance_set()
                        self.pos_time.start()
                        # self.ui.drawdown_t.setEnabled(False)
                except Exception as error:
                    self.ui.lasterror_l.setHtml(str(error))
            else:
                self.ui.lasterror_l.setHtml('Invalid Login Parameters')
        except Exception as error:
            self.ui.lasterror_l.setHtml(f'<b>{error}<b>')

    def set_prof(self):
        """
        Set Profit
        :return:
        """
        prof = 0
        if not self.calendar_e:
            self.ui.lasterror_l.setHtml("Calendar is Off By Getting Error")
            txt = "Calendar is Off By Getting Error"
            self.ui.nownews_l.setText(txt)
            # self.resize(521, 427)
            self.ui.nownews_l.show()
            # self.ui.calendar_table.hide()
            self.calendar_e = True
        try:
            if self.mt5.last_error()[1] != 'No IPC connection' and self.mt5.last_error()[1] != '':
                self.ui.connection_l.setText('Connected')
                self.ui.connection_l.setStyleSheet("color: rgb(0, 163, 0);")
                positions = self.mt5.positions_get(group='*')
                if len(positions) >= 0:
                    for i in range(0, len(positions)):
                        prof += positions[i][15]
                det = self.mt5.account_info()._asdict()
                prf = prof / float(det['balance']) * 100
                self.main_profit = prf
                self.ui.currentprofit_l.setText(f'%{round(prf, 2)}')
                if prf >= 0:
                    self.ui.currentprofit_l.setStyleSheet("color: rgb(0, 163, 0);")
                else:
                    self.ui.currentprofit_l.setStyleSheet("color: rgb(238, 17, 17);")
                dd = (float(det['equity']) - float(self.start_balance)) / float(
                    self.start_balance) * 100
                if dd > 0:
                    self.ui.drawdown_l.setStyleSheet("color: rgb(0, 163, 0);")
                else:
                    self.ui.drawdown_l.setStyleSheet("color: rgb(238, 17, 17);")
                    if abs(dd) >= abs(float(self.ui.drawdown_t.text())):
                        self.flag_do('drawdown')
                self.ui.drawdown_l.setText(f'%{round(dd, 2)}')
                if dd < 0:
                    if abs(dd) >= float(self.ui.drawdown_t.text()):
                        self.ui.lasterror_l.setHtml(f'<b><p style="color:red"> Max Draw Down Reached</p>'
                                                    f' Trading is Disabled</b>')
                        self.ui.buy.setEnabled(False)
                        self.ui.halfbuy.setEnabled(False)
                        self.ui.sell.setEnabled(False)
                        self.ui.halfsell.setEnabled(False)
            else:
                self.ui.connection_l.setText('Disconnected!')
                self.ui.connection_l.setStyleSheet("color: rgb(238, 17, 17);")
        except Exception as error:
            self.ui.lasterror_l.setHtml(str(error))


ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('trade.assitant.mt5')
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = Window()
    window.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
    window.setWindowIcon(QIcon("img/icon.png"))
    window.show()
    sys.exit(app.exec())
