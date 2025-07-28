from flask import Flask, jsonify, request
import requests
from bs4 import BeautifulSoup
import json
import pandas as pd
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"message": "Hello, World!"})

@app.route('/search', methods=['GET'])
def search():
    session = request.args.get('session')
    enrollment_time = request.args.get('enrollment_time')
    enrollment_year = request.args.get('enrollment_year')
    field = request.args.get('field')
    course = request.args.get('course')

    valid_sessions = ["Summer1", "Spring", "Winter", "Fall", "Summer2", "Summer3"]
    if session not in valid_sessions:
        return jsonify({"error": "Invalid session"}), 400

    if not enrollment_time:
        return jsonify({"error": "Enrollment time is required"}), 400

    if not enrollment_year:
        return jsonify({"error": "Enrollment year is required"}), 400

    if not field:
        return jsonify({"error": "Field is required"}), 400

    if not course:
        return jsonify({"error": "Course is required"}), 400

    try:
        year_minus_1_url = f"https://github.com/UCSD-Historical-Enrollment-Data/{int(enrollment_year) - 1}{session}/blob/main/overall/{field}%20{course}.csv?plain=1"
        year_minus_2_url = f"https://github.com/UCSD-Historical-Enrollment-Data/{int(enrollment_year) - 2}{session}/blob/main/overall/{field}%20{course}.csv?plain=1"

        response_1 = requests.get(year_minus_1_url)
        response_2 = requests.get(year_minus_2_url)

        def process_response(response):
            soup = BeautifulSoup(response.text, 'html.parser')
            script_tag = soup.find('script', {
                'type': 'application/json',
                'data-target': 'react-app.embeddedData'
            })

            if not script_tag:
                return None, "Data not found in the response"

            data_dict = json.loads(script_tag.text)
            raw_lines = data_dict.get('payload', {}).get('blob', {}).get('rawLines', [])
            if not raw_lines:
                return None, "No raw lines found in the data"

            # Create DataFrame from raw lines
            df = pd.DataFrame([line.split(',') for line in raw_lines[1:]], columns=['timestamp', 'value1', 'value2', 'value3', 'value4'])

            # Convert numeric columns to appropriate data types
            numeric_columns = ['value1', 'value2', 'value3', 'value4']
            df[numeric_columns] = df[numeric_columns].apply(pd.to_numeric, errors='coerce')

            return df, None

        df_1, error_1 = process_response(response_1)
        df_2, error_2 = process_response(response_2)

        if error_1 or error_2:
            return jsonify({"error": error_1 or error_2}), 400

        return jsonify({
            "session": session,
            "enrollment_time": enrollment_time,
            "enrollment_year": enrollment_year,
            "field": field,
            "course": course,
            "year_minus_1_url": year_minus_1_url,
            "year_minus_2_url": year_minus_2_url,
            "response_1_status": response_1.status_code,
            "response_2_status": response_2.status_code,
        })
    except ValueError:
        return jsonify({"error": "Invalid enrollment year"}), 400

# def test_search(session, enrollment_time, enrollment_year, field, course):
#     valid_sessions = ["Summer1", "Spring", "Winter", "Fall", "Summer2", "Summer3"]
#     if session not in valid_sessions:
#         return {"error": "Invalid session"}

#     if not enrollment_time:
#         return {"error": "Enrollment time is required"}

#     if not enrollment_year:
#         return {"error": "Enrollment year is required"}

#     if not field:
#         return {"error": "Field is required"}

#     if not course:
#         return {"error": "Course is required"}
#     keyword = "available"
#     try:
#         year_minus_1_url = f"https://github.com/UCSD-Historical-Enrollment-Data/{int(enrollment_year) - 1}{session}/blob/main/overall/{field}%20{course}.csv?plain=1"
#         year_minus_2_url = f"https://github.com/UCSD-Historical-Enrollment-Data/{int(enrollment_year) - 2}{session}/blob/main/overall/{field}%20{course}.csv?plain=1"
#         response_1 = requests.get(year_minus_1_url)

#         soup_1 = BeautifulSoup(response_1.text, 'html.parser')
#         script_tag = soup_1.find('script', {
#             'type': 'application/json',
#             'data-target': 'react-app.embeddedData'
#         })

#         if not script_tag:
#             return {"error": "Data not found in the response"}

#         data_dict = json.loads(script_tag.text)
#         raw_lines = data_dict.get('payload', {}).get('blob', {}).get('rawLines', [])
#         if not raw_lines:
#             return {"error": "No raw lines found in the data"}

#         # Create DataFrame from raw lines
#         df = pd.DataFrame([line.split(',') for line in raw_lines[1:]], columns=['timestamp', 'value1', 'value2', 'value3', 'value4'])

#         # Convert numeric columns to appropriate data types
#         numeric_columns = ['value1', 'value2', 'value3', 'value4']
#         df[numeric_columns] = df[numeric_columns].apply(pd.to_numeric, errors='coerce')

#         print(df)
#         return {
#             "session": session,
#             "enrollment_time": enrollment_time,
#             "enrollment_year": enrollment_year,
#             "field": field,
#             "course": course,
#             "year_minus_1_url": year_minus_1_url,
#             "year_minus_2_url": year_minus_2_url,
#             "response_1_status": response_1.status_code,
#             "data_frame": df.to_dict(orient='records')  # Return DataFrame as a list of dictionaries
#         }
#     except ValueError:
#         return {"error": "Invalid enrollment year"}

if __name__ == '__main__':
    app.run(debug=True)
# test_search("Spring", "Morning", "2025", "CSE", "100")