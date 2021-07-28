from flask import render_template, request, redirect, url_for, flash, session
import sqlite3
from datetime import date, timedelta, datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message

from app import app
from forms import *

DATABASE = 'hotel_room_allotment.db'
interval_time = ' 10:00:00'

mail= Mail(app)
app.config['MAIL_SERVER']='smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'sjcevfm@gmail.com'
app.config['MAIL_PASSWORD'] = '*************'
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
mail = Mail(app)

def check_login():
    if session.get('logged_in') != True:
        flash('Please Login')
        return False
    else:
        return True

@app.route('/logout')
def logout():
    if not check_login():
        return redirect(url_for('.home'))
    with sqlite3.connect(DATABASE) as con:
        cur = con.cursor()
        cur.execute('DELETE FROM TEMP_CART WHERE c_id="%s";'%(session['c_id']))
        con.commit()
    session.pop('logged_in', None)
    session.pop('c_id', None)
    session.pop('name', None)
    session.pop('email', None)
    session.pop('filter', None)
    session.pop('rooms', None)
    return redirect(url_for('.home'))

@app.route('/')
@app.route('/home', methods=['GET', 'POST'])
def home():
    signinform = SigninForm()
    registerform = RegisterForm()
    if request.method == 'POST':
        if 'signin' in request.form:
            if signinform.validate_on_submit():
                con = sqlite3.connect(DATABASE)
                con.row_factory = sqlite3.Row
                cur = con.cursor()
                cur.execute('SELECT c_id, name, email, password FROM CUSTOMER WHERE c_id="%s";'%(signinform.userid.data))
                user = cur.fetchone()
                con.close()
                if user:
                    if check_password_hash(user['password'], signinform.password.data):
                        session['logged_in'] = True
                        session['c_id'] = user['c_id']
                        session['name'] = user['name']
                        session['email'] = user['email']
                        return redirect(url_for('.dashboard'))
                    else:
                        flash("Invalid username or password")
                else:
                    flash("Invalid username or password")

        elif 'register' in request.form:
            if registerform.validate_on_submit():
                if registerform.password.data==registerform.repassword.data:
                    try:
                        hashed_password = generate_password_hash(registerform.password.data, method='sha256')
                        with sqlite3.connect(DATABASE) as con:
                            cur = con.cursor()
                            cur.execute('INSERT INTO CUSTOMER VALUES ("%s","%s","%s","%s","%s","%s");'%
                            (registerform.userid.data, hashed_password, registerform.name.data,
                            registerform.phone.data, registerform.email.data, registerform.aadhar.data,) )
                            con.commit()
                        msg = Message('successfully signed up', sender = 'sjcevfm@gmail.com', recipients = [registerform.email.data])
                        msg.body = '''Hello %s,
                        Thank you for signing up.
                        You can login here - https://127.0.0.1:5000%s
                        THANK YOU.'''%(registerform.name.data, url_for('.home'))
                        mail.send(msg)
                        flash("User created successfully","success")
                        return redirect(url_for('.home'))
                    except:
                        con.rollback()
                        flash("SignUp unsuccessful","warning")
                else:
                    flash("Re-entered password not matched the password","warning")

    return render_template('login.html', signinform=signinform, registerform = registerform)

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if not check_login():
        return redirect(url_for('.home'))
    con = sqlite3.connect(DATABASE)
    cur = con.cursor()
    cur.execute('SELECT DISTINCT locations FROM HOTEL;')
    locations = cur.fetchall()
    con.close()
    if request.method == "POST":
        if 'search' in request.form:
            return redirect(url_for('.hotel', location = request.form['location']))
    return render_template('dashboard.html', locations = locations)

@app.route('/hotel/<location>')
def hotel(location):
    if not check_login():
        return redirect(url_for('.home'))
    con = sqlite3.connect(DATABASE)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute('''SELECT hotel_id, hotel_name, locations, photo, AVG(star) AS avgstar
    FROM HOTEL NATURAL JOIN REVIEW WHERE locations="%s" GROUP BY hotel_id;'''%(location))
    hotels = cur.fetchall()
    con.close()
    return render_template('hotel.html', hotels = hotels, back=url_for('.dashboard'))

@app.route('/rooms/<hotel_id>', methods=['GET', 'POST'])
def room(hotel_id):
    if not check_login():
        return redirect(url_for('.home'))
    filterform = FilterForm()
    if request.method == 'GET':
        checkin = str(date.today()+timedelta(days=1))+interval_time
        checkout = str(date.today()+timedelta(days=2))+interval_time
        filterform.checkin.data = str(date.today()+timedelta(days=1))
        filterform.checkout.data = str(date.today()+timedelta(days=2))
        con = sqlite3.connect(DATABASE)
        cur = con.cursor()
        cur.execute('''SELECT room_id,room_no,price,no_beds,wifi,tv,ac FROM ROOM NATURAL JOIN TYPE
        WHERE hotel_id=%s AND room_id NOT IN
        (SELECT room_id FROM RESERVATION
        WHERE NOT ((check_in > '%s' AND check_in >= '%s') OR (check_out <= '%s' AND check_out < '%s')) );'''
        %(hotel_id,checkin,checkout,checkin,checkout) )
        rooms = cur.fetchall()
        col = [column[0] for column in cur.description]
        results = []
        for room in rooms:
            results.append(dict(zip(col, room)))
        session['rooms'] = results
        session['filter'] = {'type':filterform.type.data,'price':str(filterform.price.data),'checkin':str(filterform.checkin.data),'checkout':str(filterform.checkout.data)}
        con.close()
    if request.method == 'POST':
        if 'filter' in request.form:
            if filterform.validate_on_submit():
                type_id = filterform.type.data
                price, checkin, checkout = filterform.price.data, str(filterform.checkin.data)+interval_time, str(filterform.checkout.data)+interval_time
                if filterform.checkin.data >= filterform.checkout.data or filterform.checkin.data <= date.today():
                    flash('Invalid checkin or checkout')
                    return redirect(url_for('.room', hotel_id=hotel_id))
                con = sqlite3.connect(DATABASE)
                con.row_factory = sqlite3.Row
                cur = con.cursor()
                cur.execute('''SELECT room_id,room_no,price,no_beds,wifi,tv,ac FROM ROOM NATURAL JOIN TYPE
                WHERE type_id=%s AND price<=%s AND hotel_id=%s AND room_id NOT IN
                (SELECT room_id FROM RESERVATION
                WHERE NOT ((check_in > '%s' AND check_in >= '%s') OR (check_out <= '%s' AND check_out < '%s')) );'''
                %(type_id,price,hotel_id,checkin,checkout,checkin,checkout) )
                rooms = cur.fetchall()
                col = [column[0] for column in cur.description]
                results = []
                for room in rooms:
                    results.append(dict(zip(col, room)))
                session['rooms'] = results
                session['filter'] = {'type':filterform.type.data,'price':str(filterform.price.data),'checkin':str(filterform.checkin.data),'checkout':str(filterform.checkout.data)}
                con.close()
        elif 'choose' in request.form:
            try:
                with sqlite3.connect(DATABASE) as con:
                    cur = con.cursor()
                    checkin, checkout = request.form['check_in']+interval_time, str(request.form['check_out'])+interval_time
                    cur.execute('''SELECT COUNT(room_id) FROM TEMP_CART
                    WHERE room_id=%s AND NOT ((check_in > '%s' AND check_in >= '%s') OR (check_out <= '%s' AND check_out < '%s'));'''%
                    (request.form['room_id'], checkin, checkout, checkin, checkout))
                    if cur.fetchone()[0] == 0:
                        cur.execute('SELECT hotel_name FROM HOTEL WHERE hotel_id=%s;'%(hotel_id))
                        hotel_name = cur.fetchone()[0]
                        days = (datetime.strptime(request.form['check_out'], '%Y-%m-%d') - datetime.strptime(request.form['check_in'], '%Y-%m-%d')).days
                        cur.execute('INSERT INTO TEMP_CART VALUES ("%s",%s,"%s",%s,"%s","%s","%s",%s,%s,%s,%s);'%
                        (session['c_id'], request.form['room_id'], request.form['room_no'], float(request.form['price_amt'])*days, checkin,
                        checkout, hotel_name, request.form['beds'], request.form['wifi'], request.form['tv'], request.form['ac']) )
                        con.commit()
                    else:
                        flash("The room is blocked")
            except:
                con.rollback()
                flash("Something wrong happened while adding room to cart","warning")
        elif 'delete' in request.form:
            try:
                with sqlite3.connect(DATABASE) as con:
                    cur = con.cursor()
                    cur.execute('DELETE FROM TEMP_CART WHERE c_id="%s" AND room_id=%s;'%
                    (session['c_id'], request.form['room_id']) )
                    con.commit()
            except:
                con.rollback()
                flash("Something wrong happened while deleting room to cart","warning")
    con = sqlite3.connect(DATABASE)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute('''SELECT DISTINCT type_id, no_beds, wifi, tv, ac FROM TYPE NATURAL JOIN ROOM WHERE hotel_id=%s;'''%(hotel_id) )
    types = cur.fetchall()
    cur.execute('SELECT hotel_name, room_id, room_no, price FROM TEMP_CART WHERE c_id="%s";'%(session['c_id']))
    cart = cur.fetchall()
    cur.execute('SELECT locations FROM HOTEL WHERE hotel_id="%s";'%(hotel_id))
    location = cur.fetchone()[0]
    con.close()
    return render_template('room.html', hotel_id=hotel_id, filterform = filterform, rooms=session['rooms'], types=types,
    filter=session['filter'], cart=cart, back=url_for('.hotel', location=location))

@app.route('/confirmbooking', methods=['POST'])
def ConfirmBooking():
    if not check_login():
        return redirect(url_for('.home'))
    try:
        with sqlite3.connect(DATABASE) as con:
            cur = con.cursor()
            cur.execute('SELECT SUM(price) FROM TEMP_CART WHERE c_id="%s";'%(session['c_id']) )
            amount = cur.fetchone()[0]
            cur.execute('INSERT INTO BILL (amount, date, mode) VALUES (%s, "%s", "%s");'%(amount, datetime.now().replace(microsecond=0), request.form['mode']))
            cur.execute('SELECT last_insert_rowid();')
            bill_id = cur.fetchone()[0]
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute('SELECT * FROM TEMP_CART WHERE c_id="%s";'%(session['c_id']))
            reservations = cur.fetchall()
            for reservation in reservations:
                cur.execute('INSERT INTO RESERVATION VALUES("%s",%s,%s,"%s","%s","%s");'%(session['c_id'], bill_id, reservation['room_id'],
                reservation['check_in'], reservation['check_out'], "RESERVED"))
            cur.execute('DELETE FROM TEMP_CART WHERE c_id="%s";'%(session['c_id']))
            con.commit()
            msg = Message('Hotel reservation confirmed', sender = 'sjcevfm@gmail.com', recipients = [session['email']])
            msg.body = '''Hello %s,
            Thank you for booking rooms on our website. Your booking has been confirmed.
            You can check your bill here - https://127.0.0.1:5000%s
            THANK YOU.'''%(session['name'], url_for('.upcoming'))
            mail.send(msg)
            flash('successfully created bill','success')
    except:
        con.rollback()
        flash("Error while creating bill","warning")
    return redirect(url_for('.upcoming'))

@app.route('/upcoming', methods=['GET','POST'])
def upcoming():
    if not check_login():
        return redirect(url_for('.home'))
    if request.method=='POST':
        if 'cancel' in request.form:
            try:
                with sqlite3.connect(DATABASE) as con:
                    cur = con.cursor()
                    cur.execute('UPDATE RESERVATION SET status="CANCELLED" WHERE bill_id=%s;'%(request.form['bill_id']) )
                    con.commit()
                msg = Message('Hotel bill cancelled', sender = 'sjcevfm@gmail.com', recipients = [session['email']])
                msg.body = '''Hello %s,
                Your booking has been cancelled. However you need to pay Rs. 500.
                You can check your bill here - https://127.0.0.1:5000%s
                THANK YOU.'''%(session['name'], url_for('.cancelled'))
                mail.send(msg)
                flash("Selected bill cancelled","success")
                return redirect(url_for('.cancelled'))
            except:
                con.rollback()
                flash("Cancellation failed.","danger")
    con = sqlite3.connect(DATABASE)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute('''SELECT bill_id, date, amount, mode, check_in, check_out, room_no, price, hotel_name, locations
                FROM BILL NATURAL JOIN RESERVATION NATURAL JOIN ROOM NATURAL JOIN HOTEL
                WHERE c_id="%s" AND NOT status="CANCELLED" AND bill_id NOT IN
                (SELECT DISTINCT bill_id FROM RESERVATION WHERE check_in<="%s")
                ORDER BY (bill_id) DESC;'''%(session['c_id'], datetime.now().replace(microsecond=0)))
    bills = cur.fetchall()
    con.close()
    card = {}
    for bill in bills:
        if bill['bill_id'] in card:
            card[bill['bill_id']].append({'check_in':bill['check_in'],'check_out':bill['check_out'],'room_no':bill['room_no'],
            'price':bill['price'],'hotel_name':bill['hotel_name'],'locations':bill['locations']})
        else:
            card[bill['bill_id']] = [{'date': bill['date'], 'amount':bill['amount'], 'mode':bill['mode']}]
            card[bill['bill_id']].append({'check_in':bill['check_in'],'check_out':bill['check_out'],'room_no':bill['room_no'],
            'price':bill['price'],'hotel_name':bill['hotel_name'],'locations':bill['locations']})

    return render_template('bill_details.html', card = card, upcoming=True, back=url_for('.dashboard'))

@app.route('/cancelled')
def cancelled():
    if not check_login():
        return redirect(url_for('.home'))
    con = sqlite3.connect(DATABASE)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute('''SELECT bill_id, date, amount, mode, check_in, check_out, room_no, price, hotel_name, locations
                FROM BILL NATURAL JOIN RESERVATION NATURAL JOIN ROOM NATURAL JOIN HOTEL
                WHERE c_id="%s" AND status="CANCELLED"
                ORDER BY (bill_id) DESC;'''%(session['c_id']))
    bills = cur.fetchall()
    con.close()
    card = {}
    for bill in bills:
        if bill['bill_id'] in card:
            card[bill['bill_id']].append({'check_in':bill['check_in'],'check_out':bill['check_out'],'room_no':bill['room_no'],
            'price':bill['price'],'hotel_name':bill['hotel_name'],'locations':bill['locations']})
        else:
            card[bill['bill_id']] = [{'date': bill['date'], 'amount':bill['amount'], 'mode':bill['mode']}]
            card[bill['bill_id']].append({'check_in':bill['check_in'],'check_out':bill['check_out'],'room_no':bill['room_no'],
            'price':bill['price'],'hotel_name':bill['hotel_name'],'locations':bill['locations']})
    return render_template('bill_details.html', card = card, cancelled =True, back=url_for('.dashboard'))

@app.route('/history')
def history():
    if not check_login():
        return redirect(url_for('.home'))
    con = sqlite3.connect(DATABASE)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute('''SELECT bill_id, date, amount, mode, check_in, check_out, room_no, price, hotel_name, locations
                FROM BILL NATURAL JOIN RESERVATION NATURAL JOIN ROOM NATURAL JOIN HOTEL
                WHERE c_id="%s" AND NOT status="CANCELLED" AND bill_id IN
                (SELECT DISTINCT bill_id FROM RESERVATION WHERE check_in<="%s")
                ORDER BY (bill_id) DESC;'''%(session['c_id'], datetime.now().replace(microsecond=0)))
    bills = cur.fetchall()
    con.close()
    card = {}
    for bill in bills:
        if bill['bill_id'] in card:
            card[bill['bill_id']].append({'check_in':bill['check_in'],'check_out':bill['check_out'],'room_no':bill['room_no'],
            'price':bill['price'],'hotel_name':bill['hotel_name'],'locations':bill['locations']})
        else:
            card[bill['bill_id']] = [{'date': bill['date'], 'amount':bill['amount'], 'mode':bill['mode']}]
            card[bill['bill_id']].append({'check_in':bill['check_in'],'check_out':bill['check_out'],'room_no':bill['room_no'],
            'price':bill['price'],'hotel_name':bill['hotel_name'],'locations':bill['locations']})

    return render_template('bill_details.html', card = card, history =True, back=url_for('.dashboard'))

@app.route('/review/<hotel_id>', methods=['GET','POST'])
def review(hotel_id):
    if not check_login():
        return redirect(url_for('.home'))
    reviewform = reviewForm()
    if request.method == 'POST':
        if 'rate' in request.form:
            if reviewform.validate_on_submit():
                try:
                    with sqlite3.connect(DATABASE) as con:
                        cur = con.cursor()
                        cur.execute('INSERT INTO REVIEW (star, details, hotel_id) VALUES(%s,"%s",%s);'%
                        (reviewform.star.data, reviewform.details.data, hotel_id) )
                        con.commit()
                    flash("Your review added","success")
                except:
                    con.rollback()
                    flash("Error while adding review","warning")
    con = sqlite3.connect(DATABASE)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute('SELECT star, details FROM REVIEW WHERE hotel_id=%s ORDER BY review_id DESC;'%(hotel_id))
    reviews = cur.fetchall()
    cur.execute('SELECT locations FROM HOTEL WHERE hotel_id=%s'%(hotel_id))
    location = cur.fetchone()[0]
    con.close()
    return render_template('review.html', reviews=reviews, reviewform=reviewform, hotel_id=hotel_id, back=url_for('hotel', location=location))

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/profile', methods=['GET','POST'])
def profile():
    if not check_login():
        return redirect(url_for('.home'))
    con = sqlite3.connect(DATABASE)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute('SELECT password, phone, aadhar_no FROM CUSTOMER WHERE c_id="%s";'%(session['c_id']))
    profile = cur.fetchone()
    con.close()
    profileform = profileForm()
    if request.method == 'POST':
        if profileform.validate_on_submit():
            if check_password_hash(profile['password'], profileform.oldpassword.data):
                print('')
            else:
                flash("old password didnt match")
    return render_template('profile.html', profile = profile, profileform=profileform, back=url_for('.dashboard'))
