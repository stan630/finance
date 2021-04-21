import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
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
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user = session["user_id"]
    
    rows = db.execute("""
    SELECT symbol, SUM(shares) as totShares
    FROM transactions
    WHERE user_id = ?  GROUP BY symbol HAVING totShares > 0""", user)

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

    cash_balance = db.execute("SELECT cash from users where id = ?", user)

    # get value from dictionary inside a list
    cash_balance = cash_balance[0]['cash']
    grand_total += cash_balance

    return render_template("index.html", holdings=holdings, cash_balance=usd(cash_balance), grand_total=usd(grand_total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Symbol missing", 403)
        shares = request.form.get("shares")
        if not shares:
            return apology("Number of shares missing", 403)
        try:
            shares = int(shares)
            if shares < 0:
                return apology("Shares must be a positive number")
        except:
            return apology("Shares must be a positive number")

        user = session["user_id"]

        response = lookup(symbol.upper())
        if response == None:
            return apology("Symbol not listed.")
        company = response['name']
        currentPrice = float(response['price'])
        cash_balance = db.execute("SELECT cash from users where id = ?", user)
        # get value from dictionary inside a list
        cash_balance = cash_balance[0]['cash']
        cost = currentPrice * int(shares)
        updated_cash = cash_balance - cost
        if updated_cash < 0:
            return apology("You don't have enough cash in your account.", 403)

        # Update tables
        db.execute("UPDATE users SET cash = ? where id= ?", updated_cash, user)
        
        db.execute(
            """ INSERT INTO transactions(user_id, symbol, shares, price)
            VALUES(?,?,?,?)""", user, symbol, shares, currentPrice)

        rows = db.execute("""
        SELECT symbol, SUM(shares) as totShares
        FROM transactions
        WHERE user_id = ? GROUP BY symbol
        HAVING totShares > 0""", user)

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
            grand_total += (response["price"] * row["totShares"])

        grand_total = grand_total + updated_cash
        
        return render_template('index.html', holdings=holdings,  cash_balance=usd(updated_cash),  grand_total=usd(grand_total), shares=shares, company=company, message="Bought")
    else:
        return render_template("buy.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("symbol missing")
        sellShares = request.form.get("shares")
        if not sellShares:
            return apology("shares missing")
        user = session["user_id"]
        sellShares = int(sellShares)
        response = lookup(symbol)
        price = (response['price'])
        company = (response['name'])
        salePrice = price * int(sellShares)
        cash_balance = db.execute("SELECT cash from users where id = ?", user)
        # get value from dictionary inside a list
        cash_balance = cash_balance[0]['cash']
        cash_balance = cash_balance + int(salePrice)
        ownedShares = db.execute("""
            SELECT symbol, SUM(shares) AS totshares FROM transactions
            WHERE user_id= ? and symbol = ?""", user, symbol)
        
        # Determines shares owned after shares are sold
        ownedShares = ownedShares[0]['totshares']
        print("Sell, owned shares: ",ownedShares)
        if int(sellShares) <= int(ownedShares):
            ownedShares = int(ownedShares) - int(sellShares)
            print("New owned shares: ",ownedShares)
            
            # Update tables with sell transaction and new cash balance
            db.execute("""UPDATE users set cash = ? WHERE id = ?""",
                    cash_balance, user)
            db.execute(
                """ INSERT INTO transactions
                (user_id, symbol, price, shares)
                VALUES(?,?,?,?)""", user, symbol, salePrice, (-1*sellShares))
                # owned Shares is correct 4/20/21
            

        else:
            return apology(f"You cannot sell {sellShares} shares, you only own {ownedShares}.")

        rows = db.execute("""
        SELECT symbol, SUM(shares) as totShares
        FROM transactions
        WHERE user_id = ? GROUP BY symbol""", user)
        print("New Shares After updated transactions: ", rows)
        # # rows is a dict inside a list with totshares  equal to what owned shares should be

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
            print("Holdings: ", holdings)
            grand_total += (response["price"] * row["totShares"])
        grand_total = grand_total + cash_balance
        return render_template('index.html', holdings=holdings, sellShares=sellShares, cash_balance=usd(cash_balance,), company=company, shares=ownedShares , grand_total=usd(grand_total), message="Sold")

    else:
        user = session["user_id"]
        symbols = db.execute("""
        SELECT symbol FROM transactions
        WHERE user_id = ? GROUP BY symbol
        HAVING SUM(shares) > 0""", user)
        count = len(symbols)
        count = count + 1
        # get value from dictionary inside a list
        justValues = [sub['symbol'] for sub in symbols]
        return render_template("sell.html", symbols=justValues)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user = session["user_id"]
    holdings = []
    rows = db.execute("""
    SELECT symbol, shares, price, trans_date
    FROM transactions
    WHERE user_id = ? """, user)
    for row in rows:
        holdings.append({
            "symbol": row["symbol"],
            "shares": row["shares"],
            "price": row["price"],
            "trans_date": row["trans_date"]
        })
    return render_template("history.html", holdings=holdings)
        
    print("History: ", holdings)
        
        
       


    return apology("TODO")


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
        rows = db.execute("SELECT * FROM users WHERE username = ?",
                          request.form.get("username"))

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


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        response = lookup(symbol.upper())
        if not response:
            return apology("Stock symbol missing or incorrect symbol.", 403)
        return render_template("quoted.html", response=response)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        password = request.form.get("password")
        confirm = request.form.get("confirmation")

        if password != confirm:
            return apology("passwords don't match", 403)

     # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?",
                          request.form.get("username"))
    # Ensure username exists and password is correct
        if len(rows) > 0:
            return apology("username already exists", 403)

        username = request.form.get("username")
        hash = generate_password_hash(password)

        db.execute(
            "INSERT INTO users (username, hash) VALUES(?,? )", username, hash)

        return render_template("login.html")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
