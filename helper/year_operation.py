import datetime
def diff_year(year):
    return datetime.datetime.now().year - year

def check_age_book(age):
    if 0 <= age <= 9:
        return "New"
    elif 9 < age <= 18:
        return "Mid Year"
    elif 18 < age <= 100:
        return "Old"
    elif age > 100:
        return "Ancient"
    else:
        return f"Invalid age: {age}"


def categorize_by_age(age):
    if 0 <= age <= 9:
        return "Child"
    elif 9 < age <= 18:
        return "Adolescent"
    elif 18 < age <= 65:
        return "Adult"
    elif 65 < age <= 150:
        return "Golden age"
    else:
        return f"Invalid age: {age}"
