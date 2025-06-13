import pandas as pd
import numpy as np
from sklearn.metrics import mean_squared_error, mean_absolute_error
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('metrics_calculation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def calculate_metrics():
    """Calculate MAE and RMSE for each share using the prediction CSV files."""
    logger.info("Starting MAE and RMSE calculation for all shares")

    # List of shares to process (matching the shares in the dashboard)
    shares = ["NABIL", "NRIC", "SHIVM", "HBL", "EBL", "SCB", "KBL", "NMB", "GBIME", "NICA", "PRVU", "SBI", "ADBL"]
    results = []

    for share in shares:
        logger.info(f"Calculating metrics for {share}")
        try:
            # Load the prediction CSV file
            data = pd.read_csv(f"combined_data_with_predictions_{share}.csv", parse_dates=['date'])
            
            # Filter historical data (where actual Close prices exist and no NaN in Predicted_Close)
            historical_data = data[data['Close'].notnull() & data['Predicted_Close'].notnull()]
            if historical_data.empty:
                logger.warning(f"No valid historical data found for {share}. Skipping.")
                continue

            # Extract actual and predicted values
            y_test = historical_data['Close'].values
            y_pred = historical_data['Predicted_Close'].values

            if len(y_test) != len(y_pred) or len(y_test) == 0:
                logger.warning(f"Invalid data for {share}. Skipping.")
                continue

            # Calculate MAE and RMSE
            mae = mean_absolute_error(y_test, y_pred)
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))

            print(f"MAE for {share}: {mae:.2f} NRP")
            print(f"RMSE for {share}: {rmse:.2f} NRP")

            logger.info(f"MAE for {share}: {mae:.2f} NRP")
            logger.info(f"RMSE for {share}: {rmse:.2f} NRP")

            # Store results
            results.append({'Share': share, 'MAE (NRP)': mae, 'RMSE (NRP)': rmse})

        except Exception as e:
            logger.error(f"Error calculating metrics for {share}: {e}")

    # Save results to Excel
    if results:
        results_df = pd.DataFrame(results)
        results_df.to_excel('stock_prediction_metrics.xlsx', index=False)
        logger.info("Saved prediction metrics to stock_prediction_metrics.xlsx")
    else:
        logger.warning("No metrics calculated. Excel file not created.")

    logger.info("Metrics calculation completed successfully")

if __name__ == "__main__":
    calculate_metrics()