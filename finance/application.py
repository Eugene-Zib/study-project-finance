import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, success, login_required, lookup, usd, escape

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

@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    show = []
    sum_total = 0
    user = db.execute("SELECT * FROM users WHERE id=:id", id=session["user_id"])

    rows = db.execute("SELECT * FROM portfolio WHERE id=:id ORDER BY symbol", id=user[0]["id"])
    for row in rows:
        quote = lookup(row["symbol"])
        total = quote["price"]*row["shares"]
        sum_total = sum_total + total
        dict={"name": quote["name"], "price": usd(quote["price"]), "shares": row["shares"], "symbol": row["symbol"], "total": usd(total)}
        show.append(dict)

    return render_template("index.html", show=show, cash=usd(user[0]["cash"]), username=user[0]["username"], cash_total=usd(user[0]["cash"]+sum_total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("You have not specified a symbol")

        if not request.form.get("shares"):
            return apology("You have not specified tne number of shares")

        quote = lookup(request.form.get("symbol"))
        if not quote:
            return apology("Invalid symbol")

        shares = int(request.form.get("shares"))
        if shares < 1:
            return apology("You did not provide an integer")

        user = db.execute("SELECT * FROM users WHERE id=:id", id=session["user_id"])

        sum_shares=shares*quote["price"]
        cash = user[0]["cash"] - sum_shares
        if cash <= 0:
            return apology("You don't have enough money to buy")

        db.execute("INSERT INTO history (id, username, symbol, transactions, shares, price, sum, datetime) VALUES(:id, :username, :symbol, :transactions, :shares, :price, :sum_shares, strftime('%Y-%m-%d %H-%M-%S', 'now'))",
        id=user[0]["id"], username=user[0]["username"], symbol=quote["symbol"], transactions="buy", shares=shares, price=quote["price"], sum_shares=sum_shares)

        rows = db.execute("SELECT * FROM portfolio WHERE id=:id", id=session["user_id"])
        if rows:
            flag = True
            for row in rows:
                if row["symbol"] == quote["symbol"]:
                    db.execute("UPDATE portfolio SET shares=:shares WHERE symbol=:symbol and id=:id",
                    id=user[0]["id"], symbol=quote["symbol"], shares=shares+row["shares"])

                    db.execute("UPDATE users SET cash=:cash WHERE id=:id", cash=cash, id=user[0]["id"])

                    flag = False
                    break

            if flag:
                db.execute("INSERT INTO portfolio (id, username, symbol, shares) VALUES(:id, :username, :symbol, :shares)",
                id=user[0]["id"], username=user[0]["username"], symbol=quote["symbol"], shares=shares)

                db.execute("UPDATE users SET cash=:cash WHERE id=:id", cash=cash, id=user[0]["id"])

        else:
            db.execute("INSERT INTO portfolio (id, username, symbol, shares) VALUES(:id, :username, :symbol, :shares)",
            id=user[0]["id"], symbol=quote["symbol"], shares=shares, username=user[0]["username"])

            db.execute("UPDATE users SET cash=:cash WHERE id=:id", cash=cash, id=user[0]["id"])

        cash = '{:.2f}'.format(cash)
        sum_shares = f'{sum_shares:,.2f}'

        return render_template("buyed.html", cash=cash, sum=sum_shares)

    else:
        return render_template("buy.html")


@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""

    username = str(request.args.get("username"))
    username = escape(username)

    if len(username) > 0:
        rows = db.execute("SELECT username FROM users WHERE username=:username", username=username)

        if len(rows) == 1:
            message = "Username "+rows[0]["username"]+" is taken"
            user={"name":rows[0]["username"], "check":False, "message":message}
            return jsonify(user)
        else:
            return jsonify(username=username, check=True, message="Username "+username+" is not used")
    else:
        return redirect("/register")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    history = []
    rows = db.execute("SELECT * FROM history WHERE id=:id", id=session["user_id"])
    if rows:
        for row in rows:
            total = row["sum"]
            dict = {"symbol":row["symbol"], "transactions":row["transactions"], "shares":row["shares"], "price":row["price"], "total":f'{total:,.2f}', "datetime":row["datetime"]}
            history.append(dict)
    else:
        return apology("You don't have any transactions yet")

    return render_template("history.html", history=history, username=rows[0]["username"],)


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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

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

        if not request.form.get("symbol"):
            return apology("symbol not found")

        quote = lookup(request.form.get("symbol"))
        if not quote:
            return apology("invalid symbol")

        return render_template("quoted.html", quotes=quote)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    session.clear()

    if request.method == "POST":

        if not request.form.get("username"):
            return apology("must provide username")

        elif not request.form.get("password"):
            return apology("must provide password")

        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords don't confirmed, enter the username and password again")

        username=escape(request.form.get("username"))
        rows=db.execute("SELECT * FROM users WHERE username=:username",
                        username=username)
        if len(rows) != 0 and rows[0]["username"] == username:
            return apology("a user with the same name already exists")

        hash_password=generate_password_hash(request.form.get("password"))
        number_id=db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)",
                             username=username, hash=hash_password)

        session["user_id"]=number_id

        return success("You registered successed as "+username)

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("You must provide a symbol")

        if not request.form.get("shares"):
            return apology("You must provide the number of shares")

        if int(request.form.get("shares")) < 1:
            return apology("You did not provide an iteger")

        quote = lookup(request.form.get("symbol"))
        if not quote:
            return apology("Invalid symbol")

        user = db.execute("SELECT * FROM users WHERE id=:id", id=session["user_id"])
        shares = int(request.form.get("shares"))
        sum_shares = shares * quote["price"]
        cash = user[0]["cash"] + sum_shares

        rows = db.execute("SELECT * FROM portfolio WHERE id=:id", id=session["user_id"])
        if rows:
            flag = True
            for row in rows:
                if quote["symbol"] == row["symbol"]:
                    flag = False
                    if row["shares"] > shares:
                        db.execute("INSERT INTO history (id, username, symbol, transactions, shares, price, sum, datetime) VALUES(:id, :username, :symbol, :transactions, :shares, :price, :sum_shares, strftime('%Y-%m-%d %H-%M-%S', 'now'))",
                        id=user[0]["id"], username=user[0]["username"], symbol=quote["symbol"], transactions="sell", shares=shares, price=quote["price"], sum_shares=sum_shares)

                        db.execute("UPDATE portfolio SET shares=:shares WHERE symbol=:symbol and id=:id",
                        id=user[0]["id"], symbol=row["symbol"], shares=row["shares"]-shares)

                        db.execute("UPDATE users SET cash=:cash WHERE id=:id", cash=cash, id=session["user_id"])

                        break

                    if row["shares"] == shares:
                        db.execute("INSERT INTO history (id, username, symbol, transactions, shares, price, sum, datetime) VALUES(:id, :username, :symbol, :transactions, :shares, :price, :sum_shares, strftime('%Y-%m-%d %H-%M-%S', 'now'))",
                        id=user[0]["id"], username=user[0]["username"], transactions="sell", symbol=quote["symbol"], shares=shares, price=quote["price"], sum_shares=sum_shares)

                        db.execute("DELETE FROM portfolio WHERE symbol=:symbol and id=:id",
                        id=user[0]["id"], symbol=row["symbol"])

                        db.execute("UPDATE users SET cash=:cash WHERE id=:id", cash=cash, id=session["user_id"])

                        break

                    else:
                        return apology("You don't have the required number of shares")

            if flag:
                return apology("You don't have these shares")
        else:
            return apology("You don't have any shares")

        return redirect("/sell")

    else:
        return render_template("sell.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

