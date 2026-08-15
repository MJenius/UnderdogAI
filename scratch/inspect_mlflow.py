import sqlite3
import pandas as pd

def inspect_db():
    conn = sqlite3.connect('mlflow.db')
    
    query = """
    SELECT 
        r.run_uuid,
        t.value as run_name,
        MAX(CASE WHEN m.key = 'posterior_log_loss' THEN m.value END) as log_loss,
        MAX(CASE WHEN m.key = 'brier_calibration_error' THEN m.value END) as brier_calibration_error,
        MAX(CASE WHEN m.key = 'upset_count' THEN m.value END) as upset_count,
        MAX(CASE WHEN m.key = 'upset_rate' THEN m.value END) as upset_rate,
        MAX(CASE WHEN m.key = 'average_treatment_effect' THEN m.value END) as ate,
        MAX(CASE WHEN m.key = 'refutation_placebo_new_effect' THEN m.value END) as ref_placebo,
        MAX(CASE WHEN m.key = 'refutation_random_new_effect' THEN m.value END) as ref_random
    FROM runs r
    LEFT JOIN tags t ON r.run_uuid = t.run_uuid AND t.key = 'mlflow.runName'
    LEFT JOIN metrics m ON r.run_uuid = m.run_uuid
    GROUP BY r.run_uuid;
    """
    
    df = pd.read_sql_query(query, conn)
    print(df.to_string())
    conn.close()

if __name__ == '__main__':
    inspect_db()
