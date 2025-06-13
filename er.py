import pandas as pd
import numpy as np
from sklearn.metrics import mean_squared_error, mean_absolute_error
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('prediction_engine.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Simulated data based on the NRIC graph (approximated points)
dates = pd.date_range(start="2025-01-01", end="2025-03-01", freq='15D')
actual_prices = [420, 440, 460, 500, 451.27]  # Approximated from the graph
data = pd.DataFrame({
    'date': dates,
    'Close': actual_prices,
    'Daily_Return': np.random.normal(0, 0.01, len(dates)),
    'MA5': np.random.normal(450, 20, len(dates)),
    'MA20': np.random.normal(450, 30, len(dates)),
    'Volatility': np.random.normal(0.02, 0.005, len(dates)),
    'combined_sentiment': np.random.normal(0, 1, len(dates))
})
data.set_index('date', inplace=True)

# Define the PredictionEngine class (simplified for this example)
class PredictionEngine:
    def __init__(self, data):
        self.data = data.copy()
        self.y_test = None
        self.y_pred = None
        self.test_dates = None

    def prepare_data(self):
        # Simple train-test split (80-20)
        train_size = int(len(self.data) * 0.8)
        self.train_df = self.data[:train_size]
        self.test_df = self.data[train_size:]
        self.y_test = self.test_df['Close'].values
        self.test_dates = self.test_df.index
        logger.info(f"Training set size: {len(self.train_df)}, Testing set size: {len(self.test_df)}")
        return True

    def train_model(self):
        # Simulate a simple prediction (e.g., using the last training value as prediction)
        last_train_value = self.train_df['Close'].iloc[-1]
        self.y_pred = np.full(len(self.y_test), last_train_value)
        logger.info("Model trained with simple prediction (last train value)")
        return True

    def evaluate_model(self):
        try:
            # Calculate metrics
            mse = mean_squared_error(self.y_test, self.y_pred)
            rmse = np.sqrt(mse)
            mae = mean_absolute_error(self.y_test, self.y_pred)

            logger.info(f"Performance Metrics:")
            logger.info(f"MSE: {mse:.2f}")
            logger.info(f"RMSE: {rmse:.2f}")
            logger.info(f"MAE: {mae:.2f}")

            return True
        except Exception as e:
            logger.error(f"Error evaluating model: {e}")
            return False

# Instantiate and run
engine = PredictionEngine(data)
if engine.prepare_data():
    if engine.train_model():
        engine.evaluate_model()