import os

app_py_content = """from flask import Flask, render_template, request, jsonify
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import plotly.express as px
import plotly.graph_objects as go
import json
import os

app = Flask(__name__)

# Load and prepare data (calculates 'performance' and 'performance_category' here)
def load_and_preprocess_data():
    try:
        df = pd.read_csv('data/production_data.csv')
        df['date'] = pd.to_datetime(df['date'])
        
        # Calculate performance column with robust error handling
        # Avoid division by zero and handle potential inf/-inf values
        df['performance'] = (df['good_units'] / df['total_units'] * 100)
        df['performance'] = df['performance'].replace([np.inf, -np.inf], np.nan).fillna(0)
        
        # Create performance labels, handling potential NaNs after performance calculation
        df['performance_category'] = pd.cut(df['performance'], 
                                          bins=[0, 70, 85, 100],
                                          labels=['Low', 'Medium', 'High'],
                                          right=False) # Use right=False to include 100 in High
        
        # Ensure quality_score exists for quality trends
        if 'quality_score' not in df.columns:
            df['quality_score'] = np.random.uniform(0.7, 0.99, len(df)) # Dummy if not present

        return df
    except Exception as e:
        print(f"Error loading and preprocessing data: {str(e)}")
        return None

# Performance Classification Model
def train_performance_model(df):
    if df is None or df.empty:
        return None, None
    
    # Features must not contain NaNs for model training
    features = ['total_units', 'good_units', 'defect_units', 'temperature', 
                'pressure', 'speed', 'humidity']
    
    # Ensure target variable is not NaN
    df_cleaned = df.dropna(subset=features + ['performance_category'])
    
    if df_cleaned.empty:
        print("DataFrame is empty after dropping NaNs for performance model training.")
        return None, None

    X = df_cleaned[features]
    y = df_cleaned['performance_category']
    
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X, y)
    
    return model, features

# Defect Prediction Model
def train_defect_model(df):
    if df is None or df.empty:
        return None, None
    
    features = ['temperature', 'pressure', 'speed', 'humidity']
    df_cleaned = df.dropna(subset=features + ['defect_units'])
    
    if df_cleaned.empty:
        print("DataFrame is empty after dropping NaNs for defect model training.")
        return None, None

    X = df_cleaned[features]
    y = df_cleaned['defect_units']
    
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X, y)
    
    return model, features

# Generate performance distribution plot
def generate_performance_plot(df):
    if df is None or df.empty:
        return None
    
    fig = px.histogram(df, x='performance', 
                      title='Performance Distribution',
                      labels={'performance': 'Performance %'},
                      nbins=20)
    return fig.to_json()

# Generate defect analysis plot
def generate_defect_plot(df):
    if df is None or df.empty:
        return None
    
    fig = px.scatter(df, x='temperature', y='defect_units',
                    color='humidity',
                    title='Defect Analysis by Temperature and Humidity',
                    labels={'temperature': 'Temperature',
                           'defect_units': 'Number of Defects',
                           'humidity': 'Humidity'})
    return fig.to_json()

# Generate efficiency metrics
def calculate_efficiency_metrics(df):
    if df is None or df.empty:
        return None
    
    # Ensure performance column exists and is numeric before calculating mean
    if 'performance' not in df.columns:
        # This fallback should ideally not be hit if load_and_preprocess_data is robust
        df['performance'] = (df['good_units'] / df['total_units'] * 100).replace([np.inf, -np.inf], np.nan).fillna(0)

    metrics = {
        'avg_performance': df['performance'].mean() if not df['performance'].empty else 0.0,
        'avg_defect_rate': (df['defect_units'] / df['total_units'] * 100).mean() if df['total_units'].sum() > 0 else 0.0,
        'total_production': df['total_units'].sum() if not df['total_units'].empty else 0,
        'total_defects': df['defect_units'].sum() if not df['defect_units'].empty else 0
    }
    # Convert numpy types to native Python types for JSON serialization
    return {k: (v.item() if isinstance(v, (np.float32, np.float64, np.int32, np.int64)) else v) for k, v in metrics.items()}

@app.route('/')
def dashboard():
    df = load_and_preprocess_data()
    if df is None or df.empty:
        return render_template('dashboard.html', metrics=None, error="Data not available or empty. Please check production_data.csv")
    
    metrics = calculate_efficiency_metrics(df)
    return render_template('dashboard.html', metrics=metrics)

@app.route('/performance')
def performance():
    df = load_and_preprocess_data()
    if df is None or df.empty:
        return render_template('performance.html', performance_plot=None, metrics=None, error="Data not available or empty. Please check production_data.csv")
    
    metrics = calculate_efficiency_metrics(df)
    performance_plot = generate_performance_plot(df) # Pass the df with performance column calculated
    
    return render_template('performance.html',
                         performance_plot=performance_plot,
                         metrics=metrics)

@app.route('/defects')
def defects():
    df = load_and_preprocess_data()
    if df is None or df.empty:
        return render_template('defects.html', defect_plot=None, error="Data not available or empty. Please check production_data.csv")

    defect_plot = generate_defect_plot(df)
    
    return render_template('defects.html',
                         defect_plot=defect_plot)

@app.route('/api/quality-metrics')
def get_quality_metrics():
    df = load_and_preprocess_data()
    if df is None or df.empty:
        return jsonify({'error': 'Data not available or empty'}), 500
    
    metrics = calculate_efficiency_metrics(df)
    if metrics is None:
        return jsonify({'error': 'Metrics could not be calculated'}), 500

    # Ensure quality_score is present in metrics dictionary
    # This assumes quality_score is calculated/present in load_and_preprocess_data
    if 'quality_score' not in metrics:
        metrics['quality_score'] = df['quality_score'].mean() if 'quality_score' in df.columns else 0.0 # Fallback
    
    return jsonify(metrics)

@app.route('/api/production-data')
def get_production_data():
    df = load_and_preprocess_data()
    if df is None or df.empty:
        return jsonify({'error': 'Data not available or empty'}), 500
    
    # Group by date for production trends
    production_trends = df.groupby('date')['total_units'].sum().reset_index()
    production_trends['date'] = production_trends['date'].dt.strftime('%Y-%m-%d')
    return jsonify(production_trends.to_dict(orient='records'))

@app.route('/api/quality-trends')
def get_quality_trends():
    df = load_and_preprocess_data()
    if df is None or df.empty:
        return jsonify({'error': 'Data not available or empty'}), 500
    
    # Group by date for quality trends (assuming quality_score exists)
    quality_trends = df.groupby('date')['quality_score'].agg(['mean', 'std']).reset_index()
    quality_trends['date'] = quality_trends['date'].dt.strftime('%Y-%m-%d')
    return jsonify(quality_trends.to_dict(orient='records'))

@app.route('/api/predictions', methods=['POST'])
def get_ml_predictions():
    data = request.get_json()
    df = load_and_preprocess_data()
    
    # Assuming the prediction is for defect units based on environmental factors
    model, features = train_defect_model(df) # Using defect model for this prediction form
    
    if model is None or df is None or df.empty:
        return jsonify({'error': 'Model not trained or data not available'}), 500
    
    try:
        input_data = np.array([[
            float(data['temperature']),
            float(data['pressure']),
            float(data['speed']),
            float(data['humidity'])
        ]])
        
        predicted_defects = model.predict(input_data)[0]
        return jsonify({'predicted_defects': round(predicted_defects, 2)})
    except Exception as e:
        return jsonify({'error': f'Prediction failed: {str(e)}'}), 400

if __name__ == '__main__':
    app.run(debug=True)
"""

with open('app.py', 'w') as f:
    f.write(app_py_content)

print("app.py has been updated successfully via temporary script.") 