from flask import Flask, render_template, redirect, url_for, request
from flask_bootstrap import Bootstrap
import datetime as dt
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, IntegerField
from wtforms.validators import DataRequired, NumberRange, InputRequired
import pandas as pd
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(32)
Bootstrap(app)

# Connect to Database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tasks.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# Create Database
class RecurringTasks(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_name = db.Column(db.String(250), nullable=False)
    recurrence = db.Column(db.String(5), nullable=False)
    frequency = db.Column(db.Integer, nullable=False)
    last_passed_date = db.Column(db.DateTime, nullable=False)


class CurrentTasks(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_name = db.Column(db.String(250), nullable=False)
    task_list = db.Column(db.String(5), nullable=False)
    due_date = db.Column(db.DateTime, nullable=False)
    repeats = db.Column(db.Integer, nullable=False)


class CompletedTasks(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_name = db.Column(db.String(250), nullable=False)
    completed_date = db.Column(db.DateTime, nullable=False)


with app.app_context():
    db.create_all()


class AddTaskForm(FlaskForm):
    task_name = StringField("Task: ", validators=[DataRequired()])
    task_list = SelectField("Task List: ", choices=["Daily", "Weekly", "Monthly", "Annual"])
    is_recurring = SelectField("Is this a recurring task?", choices=["Yes", "No"], validators=[InputRequired()])
    frequency = IntegerField("How many times per day/week/month/year?", validators=[InputRequired(), NumberRange(min=1)])
    submit = SubmitField("Add Task")


class EditTaskForm(FlaskForm):
    task_name = StringField("Task: ", validators=[DataRequired()])
    task_list = SelectField("Task List: ", choices=["Daily", "Weekly", "Monthly", "Annual"])
    frequency = IntegerField("How many times per day/week/month/year?", validators=[InputRequired(), NumberRange(min=1)])
    submit = SubmitField("Update Task")


def check_date(today):
    """Checks date tasks were last updated"""
    with open("date.txt", "r") as file:
        date = file.read()
        if date == str(today):
            return False
        else:
            return True


def update_date(today):
    """Updates text file with date tasks were last updated"""
    with open("date.txt", "w") as file:
        file.write(str(today))


def create_task(recurring_task, date):
    new_task = CurrentTasks(task_name=recurring_task.task_name,
                            task_list=recurring_task.recurrence,
                            due_date=date,
                            repeats=1)
    return new_task


@app.route("/", methods=["GET", "POST"])
def home():
    """Renders home page with task lists"""

    form = AddTaskForm()
    current_date = dt.datetime.now()
    rounded_date = current_date.replace(hour=0, minute=0, second=0, microsecond=0)

    # Check whether tasks have already been updated today
    updates_required = check_date(today=rounded_date)
    if updates_required:

        # Check status of recurring tasks and pass to current list if needed
        all_recurring_tasks = RecurringTasks.query.all()
        for task in all_recurring_tasks:
            if task.recurrence == "Annual":
                if rounded_date.year > task.last_passed_date.year:
                    years = pd.date_range(start=task.last_passed_date, end=rounded_date, freq="YS").to_list()
                    if task.last_passed_date.month == 1 and task.last_passed_date.day == 1:
                        years = years[1:]
                    if len(years) > 0:
                        for year in years:
                            for i in range(0, task.frequency):
                                new_current_task = create_task(task, year)
                                db.session.add(new_current_task)
            elif task.recurrence == "Monthly":
                if rounded_date.month > task.last_passed_date.month:
                    months = pd.date_range(start=task.last_passed_date, end=rounded_date, freq="MS").to_list()
                    if task.last_passed_date.day == 1:
                        months = months[1:]
                    if len(months) > 0:
                        for month in months:
                            for i in range(0, task.frequency):
                                new_current_task = create_task(task, month)
                                db.session.add(new_current_task)
            elif task.recurrence == "Weekly":
                if rounded_date.day > task.last_passed_date.month:
                    weeks = pd.date_range(start=task.last_passed_date, end=rounded_date, freq="W-MON").to_list()
                    if task.last_passed_date.weekday() == 0:
                        weeks = weeks[1:]
                    for week in weeks:
                        for i in range(0, task.frequency):
                            new_current_task = create_task(task, week)
                            db.session.add(new_current_task)
            elif task.recurrence == "Daily":
                if rounded_date.day - task.last_passed_date.day >= 1:
                    days = pd.date_range(start=task.last_passed_date, end=rounded_date, freq="D").to_list()
                    days = days[1:]
                    if len(days) > 0:
                        for day in days:
                            for i in range(0, task.frequency):
                                new_current_task = create_task(task, day)
                                db.session.add(new_current_task)
            task.last_passed_date = rounded_date
        db.session.commit()
        update_date(today=rounded_date)

    # Add new task
    if request.method == "POST":
        if form.validate_on_submit:
            frequency = int(request.form.get("frequency"))
            if request.form.get("is_recurring") == "Yes":
                new_recurring_task = RecurringTasks(task_name=request.form.get("task_name"),
                                                    recurrence=request.form.get("task_list"),
                                                    frequency=frequency,
                                                    last_passed_date=rounded_date)
                db.session.add(new_recurring_task)
            for i in range(0, frequency):
                new_current_task = CurrentTasks(task_name=request.form.get("task_name"),
                                                task_list=request.form.get("task_list"),
                                                due_date=rounded_date,
                                                repeats=1)
                db.session.add(new_current_task)

    db.session.commit()

    # Create task lists
    daily_tasks = CurrentTasks.query.filter_by(task_list="Daily").all()
    weekly_tasks = CurrentTasks.query.filter_by(task_list="Weekly").all()
    monthly_tasks = CurrentTasks.query.filter_by(task_list="Monthly").all()
    yearly_tasks = CurrentTasks.query.filter_by(task_list="Annual").all()

    return render_template("index.html", year_list=yearly_tasks, month_list=monthly_tasks, week_list=weekly_tasks,
                           day_list=daily_tasks, form=form)


@app.route("/complete-task/<int:id>")
def mark_complete(id):
    completed_task = CurrentTasks.query.filter_by(id=id).first()
    current_date = dt.datetime.now()
    rounded_date = current_date.replace(hour=0, minute=0, second=0, microsecond=0)
    new_archived_task = CompletedTasks(task_name=completed_task.task_name,
                                       completed_date=rounded_date)
    db.session.delete(completed_task)
    db.session.add(new_archived_task)
    db.session.commit()
    return redirect(url_for("home"))


@app.route("/delete-task/<int:id>")
def delete_task(id):
    deleted_task = CurrentTasks.query.filter_by(id=id).first()
    db.session.delete(deleted_task)
    db.session.commit()
    return redirect(url_for("home"))


@app.route("/delete-recurring-task/<int:id>")
def delete_recurring(id):
    deleted_task = RecurringTasks.query.filter_by(id=id).first()
    db.session.delete(deleted_task)
    db.session.commit()
    return redirect(url_for("home"))


@app.route("/edit-recurring/<int:id>", methods=["GET", "POST"])
def edit_recurring(id):
    task_to_edit = RecurringTasks.query.filter_by(id=id).first()
    form = EditTaskForm()
    form.task_name.data = task_to_edit.task_name
    form.task_list.data = task_to_edit.recurrence
    form.frequency.data = task_to_edit.frequency

    if request.method == "POST":
        if form.validate_on_submit():
            task_to_edit.task_name = request.form.get("task_name")
            task_to_edit.recurrence = request.form.get("task_list")
            task_to_edit.frequency = request.form.get("frequency")
            db.session.commit()

            return redirect(url_for("show_recurring"))

    return render_template("edit.html", form=form)


@app.route("/move-up/<int:id>")
def move_up(id):
    """Moves a task up a level"""
    task_to_move = CurrentTasks.query.filter_by(id=id).first()
    if task_to_move.task_list == "Daily":
        new_list = "Weekly"
    elif task_to_move.task_list == "Weekly":
        new_list = "Monthly"
    elif task_to_move.task_list == "Monthly":
        new_list = "Annual"
    task_to_move.task_list = new_list
    db.session.commit()
    return redirect(url_for("home"))


@app.route("/move-down/<int:id>")
def move_down(id):
    """Moves a task down a level"""
    task_to_move = CurrentTasks.query.filter_by(id=id).first()
    if task_to_move.task_list == "Annual":
        new_list = "Monthly"
    elif task_to_move.task_list == "Monthly":
        new_list = "Weekly"
    elif task_to_move.task_list == "Weekly":
        new_list = "Daily"
    task_to_move.task_list = new_list
    db.session.commit()
    return redirect(url_for("home"))


@app.route("/archive")
def archive():
    """Displays archive of completed tasks"""
    dates = []
    archived_tasks = {}
    for item in CompletedTasks.query.distinct(CompletedTasks.completed_date):
        dates.append(item.completed_date)
    for date in dates:
        completed_tasks = CompletedTasks.query.filter_by(completed_date=date).all()
        completed_tasks_list = [task.task_name for task in completed_tasks]
        archived_tasks[date] = completed_tasks_list
    return render_template("archive.html", dict=archived_tasks)


@app.route("/view-recurring")
def show_recurring():
    """Shows recurring tasks with option to edit or delete"""
    yearly_recurring = RecurringTasks.query.filter_by(recurrence="Annual").all()
    monthly_recurring = RecurringTasks.query.filter_by(recurrence="Monthly").all()
    weekly_recurring = RecurringTasks.query.filter_by(recurrence="Weekly").all()
    daily_recurring = RecurringTasks.query.filter_by(recurrence="Daily").all()
    return render_template("recurring.html", year_list=yearly_recurring, month_list=monthly_recurring,
                           week_list=weekly_recurring, day_list=daily_recurring)


# Run app
if __name__ == "__main__":
    app.run(debug=True)
