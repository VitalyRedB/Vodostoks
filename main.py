from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length
from flask_sqlalchemy import SQLAlchemy

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime, timedelta

# считываем и формируем пересілку через телеграмм
import asyncio
from telegram import Bot
from telegram.error import TelegramError

# считываем и расшифровуем токен
from cryptography.fernet import Fernet
from dotenv import load_dotenv

import os
import glob
import asyncio

load_dotenv()
key = os.getenv("SECRET_KEY").encode()
fernet = Fernet(key)

encrypted_token = b"gAAAAABnr2Ggvg1nQmZ2TtUD0QbXyzxsN6yLn65LyBarmW4yBlyh0oRp2RysG0QSiRdzbrWewtWBJE9QH2EKfzps6s4CpRXGaDvDalGwDeEPFl4DCBt7iwkdfS6MoPEoYSbBaZZ4Iyi5"
API_TOKEN = fernet.decrypt(encrypted_token).decode()

# Telegram IDs
YOUR_ID = 6250534524 #'YOUR_TELEGRAM_ID'
BROTHER_ID = 6404929561

# Создаем объект бота
bot = Bot(token=API_TOKEN)

async def send_pdf_to_telegram(pdf_filename):
    try:
        # Отправляем сообщение
        text = f"Привет! Это тестовое сообщение от бота. 🚀\n Заявка от {session['full_name']} --> {session['phone']} "
        await bot.send_message(chat_id=YOUR_ID, text=text)
        await bot.send_message(chat_id=BROTHER_ID, text=text)
        # Отправляем файл обоим пользователям
        await bot.send_document(chat_id=YOUR_ID, document=open(pdf_filename, 'rb'))
        await bot.send_document(chat_id=BROTHER_ID, document=open(pdf_filename, 'rb'))
        # Отправляем сообщение
        text = f"Заявка на сумму {session['total_sum']} евро!!!"
        await bot.send_message(chat_id=YOUR_ID, text=text)
        await bot.send_message(chat_id=BROTHER_ID, text=text)

        # Удаляем файл после отправки
        os.remove(pdf_filename)
        print(f'Файл {pdf_filename} успешно отправлен и удален.')
    except TelegramError as e:
        print(f'Ошибка при отправке: {e}')
    except Exception as e:
        print(f'Произошла ошибка: {e}')

# Регистрируем шрифт Arial
# Укажи правильный путь к файлу Arial.ttf на твоём компьютере
arial_font_path = "Arial.ttf"  # Замени на полный путь к файлу Arial.ttf
pdfmetrics.registerFont(TTFont('Arial', arial_font_path))

# Определяем текущую директорию
current_directory = os.getcwd()
print("PDF будет сохранен в:", current_directory)

def create_pdf(filename, phone, full_name, date_registered):
    pdf = canvas.Canvas(filename, pagesize=A4)
    width, height = A4

    # Заголовок
    pdf.setFont("Arial", 14)  # Используем шрифт Arial
    pdf.drawString(50, height - 50, f"Отчет по заявке от {date_registered}")

    # Извлекаем данные из БД
    items = Item.query.all()
    data = [["ID", "Название", "Цвет", "Цена", "Кол-во", "Сумма"]]
    total_sum=0

    for item in items:
        total_price = round(item.price * item.quantity,2) if item.price and item.quantity else 0
        total_sum+=total_price
        data.append([item.id, item.title, item.color_t, item.price, item.quantity, total_price])

    # Создаем таблицу
    table = Table(data)
    table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Arial'),  # Применяем шрифт Arial ко всей таблице
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    # Рисуем таблицу на PDF
    table.wrapOn(pdf, width, height)
    table.drawOn(pdf, 50, height - 20*len(items)-150)

    # Добавляем информацию о регистрации
    pdf.setFont("Arial", 12)
    pdf.drawString(50, height - 70, f"Итоговая сумма в ЕВРО: {round(total_sum,2)}")
    pdf.drawString(50, height - 90, f"Дата регистрации: {date_registered}")
    pdf.drawString(300, height - 70, f"ФИО: {full_name}")
    pdf.drawString(300, height - 90, f"Телефон: {phone}")
    session['total_sum']=round(total_sum,2)
    pdf.save()

app = Flask(__name__)
@app.context_processor
def inject_user():
    return {
        'registered': session.get('registered', False),
        'user_data': session.get('user_data', {'phone': '', 'full_name': ''})
    }

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shops.db'  # Указываем базу данных
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
db = SQLAlchemy(app)  # Создаем объект базы данных

app.config['SECRET_KEY'] = 'mama_mama_1975'

# Форма регистрации
class RegistrationForm(FlaskForm):
    phone = StringField('Номер телефону', validators=[DataRequired(), Length(min=10, max=13)])
    full_name = StringField('Пароль (ФІО)', validators=[DataRequired()])
    submit = SubmitField('Зареєструватися')
    is_registered = False  # Новый параметр формы

@app.route('/new_register')
def new_register():
    session.clear()  # Полностью очищает session
    return redirect(url_for('register'))

# Маршрут для регистрации без базы
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()

    if request.method == 'POST':
        phone = request.form['phone']
        full_name = request.form['full_name']

            # Сохраняем данные в session
        session['user_data'] = {'phone': phone, 'full_name': full_name}
        session['phone'] = phone
        session['full_name'] = full_name
        session['registered'] = True

        flash('Данные успешно сохранены в session!')
        return redirect(url_for('show_invoice'))  # Переход на страницу профиля

    return render_template('register.html',form=form)

products = [
    {"title": "Жолоб", "price": 3.5},
    {"title": "Крючок", "price": 1.2},
    {"title": "Воронка", "price": 6},
    {"title": "Заглушка", "price": 3},
    {"title": "Кут 90", "price": 6},
    {"title": "Кут спец", "price": 8},
    {"title": "Коліно", "price": 6},
    {"title": "Труба", "price": 5},
    {"title": "Хомут", "price": 3},
    {"title": "Сніго Т_Ч", "price": 0.45},
    {"title": "Шуруп Пак", "price": 10},
    {"title": "Лента Пд", "price": 8},
    {"title": "Лента Бт", "price": 14},
    {"title": "Мембрана", "price": 31},
]

colors_id = ["8019", "8017", "XXXX", "3005", "6020", "8004", "9005", "7024", "7016", "AlZn", "Zn"]

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(20), nullable=False)
    color_t = db.Column(db.Integer, nullable=True)
    price = db.Column(db.Float, nullable=True)
    quantity = db.Column(db.Integer, nullable=True)

    isActive = db.Column(db.String(100), default="[]")  # Здесь будет храниться JSON-список [phone, full_name, date]

    def __repr__(self):
         return (
            f"<Item(\n"
            f"  id={self.id},\n"
            f"  title='{self.title}',\n"
            f"  color_t={self.color_t},\n"
            f"  price={self.price},\n"
            f"  quantity={self.quantity},\n"
            f"  isActive={self.isActive}\n"
            f")>"
        )


@app.route('/end_index', methods=['POST'])
def end_index():
    phone = session.get('phone', 'Нет данных')
    full_name = session.get('full_name', 'Нет данных')
    file_pdf = datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S') + ".pdf"
    formatted_time = (datetime.utcnow() + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')

    create_pdf(file_pdf, phone, full_name, formatted_time)
    asyncio.run(send_pdf_to_telegram(file_pdf))

    # Очистка данных после отправки PDF
    for pdf in glob.glob("*.pdf"):
        os.remove(pdf)  # Удаляем все PDF
    session.clear()  # Очищаем session
    db.session.query(Item).delete()  # Очищаем базу данных
    db.session.commit()

    flash(f'PDF {file_pdf} відравлено  та session.clear().delete()')
    return render_template('end_index.html')

@app.route('/')   #Главная страница
def index():
    return render_template('index.html')

@app.route('/about')   # Про нас
def about():
    return render_template('about.html')

@app.route('/gallery')   #  Галлеоея
def index_gallery():
    base_path = "static/imgs/gallery"
    categories = ["dah", "detal", "parkan"]
    images = {category: sorted(os.listdir(os.path.join(base_path, category)))
              for category in categories if os.path.exists(os.path.join(base_path, category))}
    return render_template('gallery.html', images=images)

@app.route('/posts')   #Заявка - данные из БазыДанных
def posts():
    articles = Item.query.all()
    return render_template('posts.html', articles=articles)


@app.route('/invoice')   #   Рахунок
def show_invoice():
    items = Item.query.all()
    total_sum = sum(round(item.price * item.quantity, 2) for item in items)
    return render_template('invoice.html', items=items, total_sum=total_sum)

@app.route('/posts/<int:id>/del')   #   Удалить позицию из БД
def post_detail(id):
    article = Item.query.get_or_404(id)
    try:
        db.session.delete(article)
        db.session.commit()
        return redirect('/posts')
    except:
        return "При видаленні запису виникла помилка"

@app.route('/posts/<int:id>')    #  Просмотр позиции в БД
def post_delete(id):
    article = Item.query.get(id)
    return render_template('post_detail.html', article=article)

@app.route('/posts/<int:id>/update', methods=['POST','GET'])   # Изменить позицию в БД
def post_update(id):
    article = Item.query.get(id)
    if request.method == "POST":
        article.title = request.form['title']
        article.color_t = request.form['color_t']
        article.price = request.form['price']
        article.quantity = request.form['quantity']

        try:
            db.session.commit() # сохраняем в БД
            return redirect('/posts') # пересылка на основную страницу
        except:
            return "При редактуванні элемента у базі данних - виникла помилка"
    else:
        return render_template('post_update.html',article=article)



@app.route('/create', methods=['POST','GET'])    #   Добавить товар в базу
def create():

    if request.method == "POST":
        title = request.form['title']
        color_t = request.form['color_t']
        price = request.form['price']
        quantity = request.form['quantity']

        item = Item(title=title, color_t=color_t, price=price, quantity=quantity)

        try:
            db.session.add(item) # добавляем обьект данных
            db.session.commit() # сохраняем в БД
            return redirect('/posts') # пересылка на основную страницу
        except Exception as e:
            db.session.rollback()  # Откатываем изменения при ошибке
            return f"Oшибка при добавлении элемента в базу данных: {e}"
    else:
        return render_template('create.html', products=products, colors_id=colors_id)

if __name__=='__main__':
    with app.app_context():
        db.create_all()  # Создаем таблицы, если их нет
    app.run(debug=True)
