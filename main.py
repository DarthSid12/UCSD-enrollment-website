from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import json
import pandas as pd
from datetime import datetime
app = Flask(__name__)
CORS(app)

enrollment_dict = {
    "2024Winter": datetime.strptime("2023-11-14T08:00", "%Y-%m-%dT%H:%M"),
    "2025Winter": datetime.strptime("2024-11-12T08:00", "%Y-%m-%dT%H:%M"),
}



@app.route('/')
def home():
    return jsonify({"message": "Hello, World!"})

@app.route('/search', methods=['GET'])
def search():

    global df_1
    
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
        past_qtr_1 = f"{int(enrollment_year) - 1}{session}"
        past_qtr_2 = f"{int(enrollment_year) - 2}{session}"

        year_minus_1_url = f"https://github.com/UCSD-Historical-Enrollment-Data/{past_qtr_1}/blob/main/overall/{field}%20{course}.csv?plain=1"
        year_minus_2_url = f"https://github.com/UCSD-Historical-Enrollment-Data/{past_qtr_2}/blob/main/overall/{field}%20{course}.csv?plain=1"

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

        with open('next_enrollment_start_time.txt', 'r') as file:
            next_enrollment_start_time = file.read()
            next_enrollment_start_datetime = datetime.strptime(next_enrollment_start_time, "%Y-%m-%dT%H:%M")
            
        enrollment_datetime = datetime.strptime(enrollment_time, "%Y-%m-%dT%H:%M")

        delta =  (enrollment_datetime - next_enrollment_start_datetime).total_seconds() / 3600

        # make the timestamp field of df_1 a difference of hours between the current record converted to datetime object and enrollment_dict[past_qtr_1]
        df_1["timestamp"] = df_1["timestamp"].apply(lambda x: (datetime.strptime(x, "%Y-%m-%dT%H:%M:%S") - enrollment_dict[past_qtr_1]).total_seconds() / 3600 - delta)
        df_2["timestamp"] = df_2["timestamp"].apply(lambda x: (datetime.strptime(x, "%Y-%m-%dT%H:%M:%S") - enrollment_dict[past_qtr_2]).total_seconds() / 3600 - delta)

        # turn the 8 variables below into a float
        df_1_value1 = float(df_1.loc[df_1["timestamp"].abs().idxmin(), "value1"])
        df_1_value2 = float(df_1.loc[df_1["timestamp"].abs().idxmin(), "value2"])
        df_1_value3 = float(df_1.loc[df_1["timestamp"].abs().idxmin(), "value3"])
        df_1_value4 = float(df_1.loc[df_1["timestamp"].abs().idxmin(), "value4"])
        
        df_2_value1 = float(df_2.loc[df_2["timestamp"].abs().idxmin(), "value1"])
        df_2_value2 = float(df_2.loc[df_2["timestamp"].abs().idxmin(), "value2"])
        df_2_value3 = float(df_2.loc[df_2["timestamp"].abs().idxmin(), "value3"])
        df_2_value4 = float(df_2.loc[df_2["timestamp"].abs().idxmin(), "value4"])

        # Generate descriptive analysis
        def generate_enrollment_analysis():
            # Calculate enrollment rates for both years
            enrollment_rate_1 = (df_1_value1 / df_1_value4) * 100 if df_1_value4 > 0 else 0
            enrollment_rate_2 = (df_2_value1 / df_2_value4) * 100 if df_2_value4 > 0 else 0
            
            # Calculate waitlist as percentage of total capacity
            waitlist_rate_1 = (df_1_value3 / df_1_value4) * 100 if df_1_value4 > 0 else 0
            waitlist_rate_2 = (df_2_value3 / df_2_value4) * 100 if df_2_value4 > 0 else 0
            
            avg_enrollment_rate = (enrollment_rate_1 + enrollment_rate_2) / 2
            avg_waitlist_rate = (waitlist_rate_1 + waitlist_rate_2) / 2
            
            # Determine risk level
            if avg_enrollment_rate >= 95 and avg_waitlist_rate > 10:
                risk_level = "high"
                risk_text = "High Risk: This course fills up quickly and has substantial waitlists at this enrollment time. Consider having backup options ready and enrolling as early as possible during your enrollment window."
            elif avg_enrollment_rate >= 85:
                risk_level = "moderate" 
                risk_text = "Moderate Risk: The course tends to fill up at this time, but you may still have a chance. Be ready to enroll right when your window opens and have alternatives prepared."
            elif avg_enrollment_rate >= 65:
                risk_level = "good"
                risk_text = "Good Chances: Based on historical data from this enrollment time, you should have a reasonable chance of getting into this course."
            else:
                risk_level = "excellent"
                risk_text = "Excellent Chances: This course typically has availability at this enrollment time, so you should be able to enroll successfully."
            
            # Determine competitiveness
            if avg_enrollment_rate >= 95:
                competitiveness = "highly competitive"
            elif avg_enrollment_rate >= 80:
                competitiveness = "moderately competitive"
            elif avg_enrollment_rate >= 60:
                competitiveness = "moderate demand"
            else:
                competitiveness = "low to moderate demand"
            
            return {
                "course_info": f"{field} {course}",
                "year_1": {
                    "quarter": past_qtr_1,
                    "enrolled": int(df_1_value1),
                    "total": int(df_1_value4),
                    "waitlist": int(df_1_value3),
                    "available": int(df_1_value2),
                    "percentage": round(enrollment_rate_1, 1)
                },
                "year_2": {
                    "quarter": past_qtr_2,
                    "enrolled": int(df_2_value1),
                    "total": int(df_2_value4),
                    "waitlist": int(df_2_value3),
                    "available": int(df_2_value2),
                    "percentage": round(enrollment_rate_2, 1)
                },
                "competitiveness": competitiveness,
                "risk_level": risk_level,
                "risk_text": risk_text,
                "avg_enrollment_rate": round(avg_enrollment_rate, 1),
                "avg_waitlist_rate": round(avg_waitlist_rate, 1)
            }

        return jsonify({
            "analysis": generate_enrollment_analysis(),
            "raw_data": {
                f"{past_qtr_1}": {
                    "enrolled": int(df_1_value1),
                    "available": int(df_1_value2),
                    "waitlist": int(df_1_value3),
                    "total_capacity": int(df_1_value4)
                },
                f"{past_qtr_2}": {
                    "enrolled": int(df_2_value1),
                    "available": int(df_2_value2),
                    "waitlist": int(df_2_value3),
                    "total_capacity": int(df_2_value4)
                }
            }
        })

    except ValueError:
        return jsonify({"error": "Invalid enrollment year"}), 400

@app.route('/df1', methods=['GET'])
def df1():
    global df_1
    return jsonify({"df1": df_1["timestamp"].to_dict()})

if __name__ == '__main__':
    app.run(debug=True)
# test_search("Spring", "Morning", "2025", "CSE", "100")