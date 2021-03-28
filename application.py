

import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template,\
     request, session, jsonify
from flask.helpers import url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"): # pk_c1ed09bf5c9a4aacb392aa5dc3a7bb04 
    raise RuntimeError("API_KEY not set")

@app.route("/")
@app.route("/index")
@login_required
def index():
    user = session["user_id"]
    rows = db.execute("""
    SELECT symbol, company, SUM(shares) as totShares
    FROM buys 
    WHERE user_id = ? GROUP BY symbol""",user)
    
    # shares = rows[0]['sum(shares)']
    holdings = []
    grand_total = 0
    for row in rows:
        response = lookup(row["symbol"])
        holdings.append({
            "symbol": response["symbol"],
            "name": response["name"],
            "shares": row["totShares"],
            "price": usd(response["price"]),
            "totCost": usd(response["price"] * row["totShares"])
        })
        grand_total += response["price"] * row["totShares"]
    cash_balance = 0
    old_balance = db.execute("SELECT cash from users where id = ?",user)
    # get value from dictionary inside a list
    cash_balance = old_balance[0]['cash']
    grand_total += cash_balance
    
    return render_template("index.html",holdings=holdings, cash_balance=usd(cash_balance), grand_total=usd(grand_total))

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)
        
        password = request.form.get("password")
        confirm = request.form.get("confirmation")

        print(password, confirm)
        
        if password != confirm:
            return apology("passwords don't match", 403)
        
     # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
    # Ensure username exists and password is correct
        if len(rows) > 0:
            return apology("username already exists", 403)

        username = request.form.get("username")
        hash = generate_password_hash(password)

        db.execute("INSERT INTO users (username, hash) VALUES(?,? )", username, hash)
        
        return render_template("login.html")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

    
    
    # return apology("Make a menu selection.")
    
@app.route("/buy",methods=["GET", "POST"] )
@login_required
def buy():
    
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Symbol missing",403)
        shares = request.form.get("shares")
        if not shares :
            return apology("Number of shares missing",403)
        try:
            shares = int(shares)
            if shares < 0:  
                return apology("Shares must be a positive number")
        except:
            return apology("Shares must be a positive number")
        
        user = session["user_id"]
       
        response = lookup(symbol.upper())
        company = response['name']
        price = response['price']
        cost= shares * price
        cash_balance = db.execute("SELECT cash from users where id = ?", user)
        # get value from dictionary inside a list
        cash_balance = cash_balance[0]['cash']
        print("cash balance: ", cash_balance)
        cash_balance = cash_balance - cost
        
        if cash_balance < 0:
            return apology("You don't have enough cash in your account.",403)
        
        db.execute("INSERT INTO buys (symbol,company, shares, price, user_id) \
        VALUES(?,?,?,?,?)", symbol, company, shares, price, user)

        rows = db.execute("""
        SELECT symbol, company, SUM(shares) as totShares
        FROM buys 
        WHERE user_id = ? GROUP BY symbol""",user)
        holdings = []
        grand_total = 0
        for row in rows:
            response = lookup(row["symbol"])
            holdings.append({
                "symbol": response["symbol"],
                "name": response["name"],
                "shares": row["totShares"],
                "price": usd(response["price"]),
                "totCost": usd(response["price"] * row["totShares"])
            })
            grand_total += response["price"] * row["totShares"]

                
        
        db.execute("UPDATE users SET cash = ? where id= ?",cash_balance,user)
        return render_template('index.html', holdings=holdings, cash_balance=usd(cash_balance,), grand_total=usd(grand_total),message="Bought")
    else:
        return render_template("buy.html")
    


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    return apology("TODO")





@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":
        symbol = request.form.get("symbol")
        response =lookup(symbol.upper())
        if not response:
            return apology("Stock symbol missing or incorrect symbol.",403)
        return render_template("quoted.html", response=response)
    else:
        return render_template("quote.html")

    
@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    return apology("TODO")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    # return apology(e.name, e.code)
    return apology("This is an apology")


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
