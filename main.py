from flask import Flask, render_template, request, url_for, redirect
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import sqlite3
import os
##################################################################################################################
# Obtener la ruta completa del archivo de la base de datos
db_file_path = os.path.join('C:\\Users\\davi2\\PycharmProjects\\Proyectos\\RSIxaWELCOME_BASEDEDATOS\\', 'users.db')
# Conectar a la base de datos o crearla si no existe
conn = sqlite3.connect(db_file_path)
cursor = conn.cursor()
# Definir la consulta SQL para crear la tabla "users"
create_table_sql = '''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT
)
'''
cursor.execute(create_table_sql)

conn.commit()
conn.close()
######################################################################################################################
app = Flask(__name__)


@app.route('/users')
def get_db_connection():
    conn = sqlite3.connect('C:\\Users\\davi2\\PycharmProjects\\Proyectos\\RSIxaWELCOME_BASEDEDATOS\\users.db')
    conn.row_factory = sqlite3.Row  # Acceder a las filas por nombre
    return conn

# Página principal
#####################################################################################################################
@app.route("/", methods=["GET", "POST"])

def welcome():
    if request.method == 'POST':
        name = request.form['name']
        db = get_db_connection()
        db.execute('INSERT INTO users (name) VALUES (?)', (name,))
        db.commit()
        db.close()
        # Redirige al usuario a la página principal.
        return redirect(url_for('index', user_name=name))
    return render_template("welcome.html")
#######################################################################################################################
@app.route("/analysis", methods=["GET", "POST"])

def index():
    user_name = request.args.get('user_name')
    if request.method == "POST":
        capital = float(request.form["capital"])
        ticker = request.form["ticker"]

        if capital > 0 and ticker:


            start_date = '2019-01-01'

            # Obtener datos de precios ajustados de Yahoo Finance
            data = yf.download(ticker, start=start_date)

            # Acceder a la columna 'Adj Close' (Cierre Ajustado)
            df = data['Adj Close']

            returns = df.pct_change()[1:]
            long_window = 14
            up = returns.clip(lower=0)
            down = -1 * returns.clip(upper=0)

            # calculo de la media con los periodos que hemos puesto (14).
            ema_up = up.ewm(span=long_window).mean()
            ema_down = down.ewm(span=long_window).mean()

            rs = ema_up / ema_down
            rsi = 100 - (100 / (1 + rs))


            signal = pd.DataFrame(index=df.index)
            signal['RSI'] = rsi

            signal['signalbuy'] = np.where(signal['RSI'] < 30, 1, 0)
            signal['positionbuy'] = signal['signalbuy'].diff()  # Cuando cruce de abajo a arriba delimita con un -1

            signal['signalsell'] = np.where(signal['RSI'] > 70, 1, 0)
            signal['positionsell'] = signal['signalsell'].diff()

            # limpiamos el dataframe
            df = df.iloc[long_window:]
            signal = signal.iloc[long_window:]

            # crearemos una tabla o DataFrame que nos permita arrastrar la situación de la cartera día a día a modo contable.

            data = pd.DataFrame()
            data['Precio'] = df
            data['signal C'] = signal['positionbuy']
            data['signal V'] = signal['positionsell']
            data['Compra'] = 0
            data['Venta'] = 0
            data['I.Compra'] = 0
            data['I.Venta'] = 0
            data['Stock'] = 0
            data['Portfolio'] = 0
            data['Cash'] = 0
            data['PyG'] = 0
            data['Comisiones'] = 0
            data = data.reset_index()  # para tener las fechas en una columna.

            orden = int(100)
            lotemin = int(10)
            # cashmin = int(100)
            cf = int(5)
            cv = 0.001
            parte = 0.5  # Ventas del 50%, despues del 50% que noshaya quedado y asi sucesivamente.


            data.loc[0, 'Cash'] = capital
            data.loc[0, 'Total'] = capital

            for x in range(len(data)):
                if x == 0:
                    x = 1
                data.loc[x, 'Cash'] = data.iloc[(x - 1), 10]
                data.loc[x, 'Stock'] = data.iloc[(x - 1), 8]
                data.loc[x, 'Portfolio'] = data.iloc[x, 8] * data.iloc[x, 1]
                data.loc[x, 'PyG'] = data.iloc[x, 10] + data.iloc[x, 9] - capital
                if (data.iloc[x, 2] == -1 and data.iloc[(x - 1), 10] > 0):
                    lote = orden
                    comfix = cf

                    if (data.iloc[(x - 1), 10]) < (lote * data.iloc[x, 1] + (cf + cv * data.iloc[x, 1] * lote)):
                        lote = (data.iloc[(x - 1), 10] - (cf + cv * data.iloc[x, 1] * orden)) // data.iloc[x, 1]
                        if lote < lotemin:
                            lote = 0
                            cf = 0
                    if data.iloc[(x - 1), 10] > (lote * data.iloc[x, 1]):
                        data.loc[x, 'I.Compra'] = lote * data.iloc[x, 1]
                        data.loc[x, 'Compra'] = lote
                        data.loc[x, 'Stock'] = lote + data.iloc[(x - 1), 8]
                        data.loc[x, 'Portfolio'] = data.iloc[x, 8] * data.iloc[x, 1]
                        data.loc[x, 'Comisiones'] = cf + cv * data.iloc[x, 6]
                        data.loc[x, 'Cash'] = data.iloc[(x - 1), 10] - data.iloc[x, 6] - data.iloc[x, 12]
                elif (data.iloc[x, 3] == -1 and data.iloc[(x - 1), 8] > 0):
                    paquete = int(data.iloc[(x - 1), 8] * parte)
                    if paquete < lotemin:
                        paquete = 0
                        cf = 0
                    data.loc[x, 'I.Venta'] = paquete * data.iloc[x, 1]
                    data.loc[x, 'Venta'] = paquete
                    data.loc[x, 'Stock'] = data.iloc[(x - 1), 8] - paquete
                    data.loc[x, 'Portfolio'] = data.iloc[x, 8] * data.iloc[x, 1]
                    data.loc[x, 'Comisiones'] = cf + cv * data.iloc[x, 7]
                    data.loc[x, 'Cash'] = data.iloc[(x - 1), 10] + data.iloc[x, 7] - data.iloc[x, 12]
                else:
                    data.loc[x, 'Portfolio'] = data.iloc[x, 8] * data.iloc[x, 1]
                    data.loc[x, 'PyG'] = data.iloc[x, 10] + data.iloc[x, 9] - capital

            data.set_index('Date', inplace=True)

            data['Total'] = (data['Portfolio'] + data['Cash'])
            data['Returns'] = data['Total'].pct_change()[1:]
            data['Returns'] = data['Returns'][data['Returns'] != 0]

            print('\n Valor total neto cash + cartera al final del periodo ', round(data['Total'][-1], 2))

            # Calcular la ganancia total al final del período
            ganancia_total = round(data['Total'][-1] - capital, 2)

            fig = plt.figure(figsize=(16, 8))
            fig.set_facecolor('#f0f0f0')
            fig.suptitle(f'Estrategia RSI: {ticker} - Ganancia Total: {ganancia_total}', fontsize=16)

            ax1 = fig.add_subplot(221, ylabel="Precio")
            ax2 = fig.add_subplot(223, ylabel="RSI")
            ax3 = fig.add_subplot(222, ylabel="Valor de la cartera")
            ax4 = fig.add_subplot(224, ylabel="Frecuencia")

            ax1.set_title("Estrategia RSI: " + str(ticker))
            ax1.get_xaxis().set_visible(False)

            df.plot(ax=ax1, color='b', lw=1.1)
            ax1.plot(df[signal['positionbuy'] == -1], '^', markersize=8, color='g')
            ax1.plot(df[signal['positionsell'] == -1], 'v', markersize=8, color='r')

            signal.RSI.plot(ax=ax2, color='b')
            ax2.set_ylim(0, 100)
            ax2.axhline(70, color='r', linestyle='--')
            ax2.axhline(30, color='r', linestyle='--')

            data.Total.plot(ax=ax3, color='b', lw=1.1)
            ax3.set_title(
                "Capital: " + str(capital) + "\nLote: " + str(orden) + "\nVentas del: " + str(parte * 100) + "%")
            ax3.plot(data['Total'][signal['positionbuy'] == -1], '^', markersize=8, color='g')
            ax3.plot(data['Total'][signal['positionsell'] == -1], 'v', markersize=8, color='r')
            sns.histplot(data['Returns'], kde=True, ax=ax4)
            # Lo guardo como imagen
            image_path = "static/plot.png"
            fig.savefig(image_path)


            return render_template("results.html", capital=capital, ticker=ticker, ganancia_total=ganancia_total)

    return render_template("index.html", user_name=user_name)

@app.route('/thanks')
def thanks():
    return render_template('thanks.html')

if __name__ == "__main__":
       app.run(debug=True)
