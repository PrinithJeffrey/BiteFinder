from flask import Flask, render_template, request, redirect, url_for, flash
from flask_mysqldb import MySQL
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)
app.secret_key = 'bbda529b87c96c1bb10db7939f86c953293092057b97f9e7'
# MySQL configuration
app.config['MYSQL_HOST'] = '127.0.0.1'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Prinith_132004'
app.config['MYSQL_DB'] = 'recipe_finder'

mysql = MySQL(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User model
class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    return User(user[0]) if user else None

# Registration form
class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

# Registration Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
        mysql.connection.commit()
        cursor.close()
        flash('Your account has been created!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

# Login form
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()
        cursor.close()
        if user:
            login_user(User(user[0]))
            return redirect(url_for('index'))
        else:
            flash('Login unsuccessful. Please check username and password.', 'danger')
    return render_template('login.html', form=form)

# Logout Route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# Home Route
@app.route('/')
@login_required
def index():
    return render_template('index.html')

# Route to submit a review
@app.route('/review/<int:recipe_id>', methods=['POST'])
@login_required
def review(recipe_id):
    review_text = request.form['review_text']
    cursor = mysql.connection.cursor()
    cursor.execute("INSERT INTO reviews (user_id, recipe_id, review_text) VALUES (%s, %s, %s)", (current_user.id, recipe_id, review_text))
    mysql.connection.commit()
    cursor.close()
    return redirect(url_for('recipe_details', recipe_id=recipe_id))

# Route to view a recipe's details along with reviews
@app.route('/recipe/<int:recipe_id>')
@login_required
def recipe_details(recipe_id):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM recipes WHERE id = %s", (recipe_id,))
    recipe = cursor.fetchone()

    cursor.execute("SELECT * FROM reviews WHERE recipe_id = %s", (recipe_id,))
    reviews = cursor.fetchall()
    cursor.close()

    # Get recommendations
    recommendations = get_recommendations(recipe_id)

    return render_template('recipe_details.html', recipe=recipe, reviews=reviews, recommendations=recommendations)

def fetch_data():
    cursor = mysql.connection.cursor()
    
    # Get recipes
    cursor.execute("SELECT id, title, description FROM recipes")
    recipes = cursor.fetchall()

    # Get reviews
    cursor.execute("SELECT recipe_id, review_text FROM reviews")
    reviews = cursor.fetchall()
    
    cursor.close()

    # Prepare DataFrame
    recipe_df = pd.DataFrame(recipes, columns=['id', 'title', 'description'])
    review_df = pd.DataFrame(reviews, columns=['recipe_id', 'review_text'])

    # Merge DataFrames
    merged_df = recipe_df.merge(review_df, left_on='id', right_on='recipe_id', how='left')
    return merged_df

def get_recommendations(recipe_id):
    merged_df = fetch_data()

    # Create TF-IDF Vectorizer
    tfidf_vectorizer = TfidfVectorizer(stop_words='english')

    # Fill NaN values with an empty string
    merged_df['review_text'] = merged_df['review_text'].fillna('')
    
    # Combine description and reviews for better results
    merged_df['combined'] = merged_df['description'] + " " + merged_df['review_text']

    # Fit and transform the combined text
    tfidf_matrix = tfidf_vectorizer.fit_transform(merged_df['combined'])

    # Compute cosine similarity
    cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)

    # Get index of the recipe that matches the recipe_id
    idx = merged_df[merged_df['id'] == recipe_id].index[0]

    # Get pairwise similarity scores of all recipes with that recipe
    sim_scores = list(enumerate(cosine_sim[idx]))

    # Sort the recipes based on similarity scores
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)

    # Get the scores of the 5 most similar recipes
    sim_scores = sim_scores[1:6]

    # Get the recipe indices
    recipe_indices = [i[0] for i in sim_scores]

    # Return the top 5 most similar recipes
    return merged_df.iloc[recipe_indices][['id', 'title']]

# Run the app
if __name__ == '__main__':
    app.run(debug=True)
