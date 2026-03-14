import joblib
import numpy as np
import pandas as pd

# Load the saved components
model = joblib.load('app/ml_models/random_forest_model.pkl')
scaler = joblib.load('app/ml_models/scaler.pkl')
city_encoder = joblib.load('app/ml_models/city_encoder.pkl')
stream_encoder = joblib.load('app/ml_models/stream_encoder.pkl')
target_encoder = joblib.load('app/ml_models/target_encoder.pkl')

# Human-readable display names for ML career labels
CAREER_DISPLAY_NAMES = {
    # Agriculture
    "Agri_Forestry": "Forestry Specialist",
    "Agri_Scientist": "Agricultural Scientist",
    # Engineering
    "Eng_Architecture": "Architect",
    "Eng_Civil_Engineer": "Civil Engineer",
    "Eng_Computer_Engineer": "Computer Engineer",
    "Eng_Electronics_Comm": "Electronics & Communication Engineer",
    "Eng_Geomatics": "Geomatics Engineer",
    "Eng_Mechanical": "Mechanical Engineer",
    # Humanities
    "Hum_Economist": "Economist",
    "Hum_Journalist": "Journalist",
    "Hum_Political_Scientist": "Political Scientist",
    "Hum_Psychologist": "Psychologist",
    "Hum_Social_Worker_BSW": "Social Worker (BSW)",
    # IT
    "IT_AI_ML_Engineer": "AI / ML Engineer",
    "IT_Cloud_Engineer": "Cloud Engineer",
    "IT_CyberSecurity": "Cybersecurity Analyst",
    "IT_Data_Scientist": "Data Scientist",
    "IT_Game_Developer": "Game Developer",
    "IT_QA_Engineer": "QA Engineer",
    "IT_Software_Engineer": "Software Engineer",
    "IT_UI_UX_Designer": "UI/UX Designer",
    # Law
    "Law_Corporate_Lawyer": "Corporate Lawyer",
    "Law_Criminal_Lawyer": "Criminal Lawyer",
    # Medical
    "Med_BDS_Dentist": "Dentist (BDS)",
    "Med_BSc_Nursing": "Nursing (BSc)",
    "Med_B_Pharmacy": "Pharmacist (B.Pharm)",
    "Med_Health_Assistant_HA": "Health Assistant (HA)",
    "Med_Lab_Technician": "Lab Technician",
    "Med_MBBS_Doctor": "Doctor (MBBS)",
    "Med_Public_Health_BPH": "Public Health (BPH)",
    "Med_Veterinary": "Veterinary Doctor",
    # Management
    "Mgmt_BBA_Finance": "Finance (BBA)",
    "Mgmt_BBA_Marketing": "Marketing (BBA)",
    "Mgmt_CA": "Chartered Accountant (CA)",
    "Mgmt_Entrepreneur": "Entrepreneur",
    "Mgmt_HR_Manager": "HR Manager",
    "Mgmt_Hotel_Mgmt_BHM": "Hotel Management (BHM)",
    "Mgmt_Supply_Chain": "Supply Chain Manager",
}

def format_career_label(raw_label: str) -> str:
    """Convert a raw ML label to a clean display name."""
    return CAREER_DISPLAY_NAMES.get(raw_label, raw_label.replace("_", " "))

def predict_career(user_json_data):
    # Standard NEB Grade to GPA translation
    grade_to_gpa = {
        "A+": 4.0, "A": 3.6, "B+": 3.2, "B": 2.8,
        "C+": 2.4, "C": 2.0, "D": 1.6, "NG": 0.0,
        "": 0.0 # for empty values
    }
    
    # helper for checking gender
    gender_map = {'Male': 1, 'Female': 0, 'Other': 0}
    income_map = {'Low': 1, 'Medium': 2, 'High': 3}

    # Extract general info
    gen_info = user_json_data.get('general_info', {})
    grades = user_json_data.get('grades', {})
    interests = user_json_data.get('interests', {})
    scores = user_json_data.get('entrance_scores', {})
    
    # Process Plus2_Stream to match encoder classes
    stream = gen_info.get('plus2_stream', 'Management')
    if stream.lower() == 'science':
        # If biology grade is present and not empty/0, it's Science_Bio
        if grades.get('biology') and str(grades.get('biology')).strip() != '':
            stream = 'Science_Bio'
        else:
            stream = 'Science_Physical'
    elif stream.lower() == 'management':
        stream = 'Management'
    elif stream.lower() == 'humanities':
        stream = 'Humanities'
    elif stream.lower() == 'law':
        stream = 'Law'
    elif stream.lower() == 'education':
        # Default or fallback since Education is not in the encoder
        stream = 'Humanities'
    else:
        stream = stream.capitalize()

    # Define the exact columns Expected by the Random Forest Model
    feature_columns = [
        'Gender', 'City_Type', 'Family_Income', 'Plus2_Stream', 'Plus2_GPA', 
        'Entrance_Score_IOE', 'Entrance_Score_CEE', 'Entrance_Score_CMAT', 
        'Grade_English', 'Grade_Nepali', 'Grade_Social', 'Grade_Math', 
        'Grade_Physics', 'Grade_Chemistry', 'Grade_Biology', 'Grade_Computer', 
        'Grade_Accounts', 'Grade_Economics', 'Grade_Law', 
        'Interest_Technology', 'Interest_Math_Stats', 'Interest_Art_Design', 
        'Interest_Business_Money', 'Interest_Social_People', 'Interest_Bio_Health', 
        'Interest_Nature_Agri', 'Interest_Construction', 'Interest_Law_Politics', 
        'Interest_Hospitality_Food', 'Interest_Gaming_Entertainment', 'Interest_History_Culture', 
        'Delta_Tech_Construction', 'Delta_Bio_Tech', 'Delta_Money_Creativity', 
        'Score_Tech', 'Score_Bio', 'Score_Biz'
    ]

    # Initialize a dict with 0.0 for all float features
    data = {col: [0.0] for col in feature_columns}
    
    # 1. Manually set specific non-float features
    data['Gender'] = [gender_map.get(gen_info.get('gender', 'Other'), 0)]
    data['City_Type'] = [gen_info.get('city_type', 'Urban')]
    data['Family_Income'] = [income_map.get(gen_info.get('family_income', 'Medium'), 2)]
    data['Plus2_Stream'] = [stream]
    data['Plus2_GPA'] = [float(gen_info.get('plus2_gpa', 0.0))]
    
    # Entrance scores
    data['Entrance_Score_IOE'] = [float(scores.get('ioe', 0.0))]
    data['Entrance_Score_CEE'] = [float(scores.get('cee', 0.0))]
    data['Entrance_Score_CMAT'] = [float(scores.get('cmat', 0.0))]
    
    # Interests (Parse all 12 categories from JSON)
    data['Interest_Technology'] = [float(interests.get('technology', 0.0))]
    data['Interest_Math_Stats'] = [float(interests.get('math_stats', 0.0))]
    data['Interest_Art_Design'] = [float(interests.get('art_design', 0.0))]
    data['Interest_Business_Money'] = [float(interests.get('business_money', 0.0))]
    data['Interest_Social_People'] = [float(interests.get('social_people', 0.0))]
    data['Interest_Bio_Health'] = [float(interests.get('bio_health', 0.0))]
    data['Interest_Nature_Agri'] = [float(interests.get('nature_agri', 0.0))]
    data['Interest_Construction'] = [float(interests.get('construction', 0.0))]
    data['Interest_Law_Politics'] = [float(interests.get('law_politics', 0.0))]
    data['Interest_Hospitality_Food'] = [float(interests.get('hospitality_food', 0.0))]
    data['Interest_Gaming_Entertainment'] = [float(interests.get('gaming_entertainment', 0.0))]
    data['Interest_History_Culture'] = [float(interests.get('history_culture', 0.0))]
    
    # Grades mapping
    data['Grade_English'] = [grade_to_gpa.get(str(grades.get('english', '')), 0.0)]
    data['Grade_Nepali'] = [grade_to_gpa.get(str(grades.get('nepali', '')), 0.0)]
    data['Grade_Math'] = [grade_to_gpa.get(str(grades.get('math', '')), 0.0)]
    data['Grade_Physics'] = [grade_to_gpa.get(str(grades.get('physics', '')), 0.0)]
    data['Grade_Chemistry'] = [grade_to_gpa.get(str(grades.get('chemistry', '')), 0.0)]
    data['Grade_Biology'] = [grade_to_gpa.get(str(grades.get('biology', '')), 0.0)]
    data['Grade_Computer'] = [grade_to_gpa.get(str(grades.get('computer', '')), 0.0)]
    data['Grade_Accounts'] = [grade_to_gpa.get(str(grades.get('accounts', '')), 0.0)]
    data['Grade_Economics'] = [grade_to_gpa.get(str(grades.get('economics', '')), 0.0)]
    
    data['Grade_Social'] = [grade_to_gpa.get(str(grades.get('social', '')), 0.0)]
    data['Grade_Law'] = [grade_to_gpa.get(str(grades.get('law', '')), 0.0)]
    
    # Add engineered features using the exact equations from your Colab notebook
    data['Delta_Tech_Construction'] = [data['Interest_Technology'][0] - data['Interest_Construction'][0]]
    data['Delta_Bio_Tech'] = [data['Interest_Bio_Health'][0] - data['Interest_Technology'][0]]
    data['Delta_Money_Creativity'] = [data['Interest_Business_Money'][0] - data['Interest_Art_Design'][0]]

    data['Score_Tech'] = [data['Grade_Computer'][0] + data['Grade_Math'][0] + data['Grade_Physics'][0]]
    data['Score_Bio'] = [data['Grade_Biology'][0] + data['Grade_Chemistry'][0]]
    data['Score_Biz'] = [data['Grade_Accounts'][0] + data['Grade_Economics'][0]]
    
    # Build DataFrame matching exact column order
    input_df = pd.DataFrame(data, columns=feature_columns)
    
    # 2. Apply the exact same encoders
    input_df['City_Type'] = city_encoder.transform(input_df['City_Type'])
    input_df['Plus2_Stream'] = stream_encoder.transform(input_df['Plus2_Stream'])
    
    # 3. Apply the exact same scaler to the score columns
    score_cols = ['Entrance_Score_IOE', 'Entrance_Score_CEE', 'Entrance_Score_CMAT']
    input_df[score_cols] = scaler.transform(input_df[score_cols])
    
    # 4. Make probability-based prediction and pick top 3 classes
    predicted_probabilities = model.predict_proba(input_df)[0]
    top_k = min(3, len(predicted_probabilities))
    top_indices = np.argsort(predicted_probabilities)[::-1][:top_k]

    # model.classes_ holds the encoded class labels for predict_proba columns
    top_encoded_classes = model.classes_[top_indices].astype(int)
    top_job_roles = target_encoder.inverse_transform(top_encoded_classes)

    # Format the labels to be human-readable
    return [format_career_label(role) for role in top_job_roles.tolist()]
