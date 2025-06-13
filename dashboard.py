from flask import Flask, render_template_string, Response
from data_ingestion import DataIngestion
from dataprocessing import DataProcessor
from prediction_engine import PredictionEngine
import logging
import json
from datetime import datetime, time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_ingestion.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class Dashboard:
    def __init__(self):
        self.ingestion = DataIngestion()
        self.processor = DataProcessor()
        self.predictor = PredictionEngine()
        self.live_update = False
        self.data = None
        # Updated image URL with a fallback if the original fails
        self.image_url = "https://images.unsplash.com/photo-1590283603385-4b7db7c40a5a?ixlib=rb-4.0.3&auto=format&fit=crop&w=1350&q=80"

    def is_market_open(self):
        try:
            now = datetime.now()
            current_time = now.time()
            current_day = now.weekday()  # 0 = Monday, 5 = Saturday, 6 = Sunday
            market_open = time(10, 0)  # 10:00 AM
            market_close = time(15, 45)  # 3:45 PM
            is_holiday = current_day in [4, 5]  # Friday (4), Saturday (5)
            result = not is_holiday and market_open <= current_time <= market_close
            logger.info(f"Market open check: {result} (Time: {current_time}, Day: {current_day})")
            return result
        except Exception as e:
            logger.error(f"Error in is_market_open: {e}")
            return False

    def get_dashboard_data(self, share):
        try:
            # If market is closed, return last cached data without updating
            if not self.is_market_open():
                logger.warning("Market is closed or it's a holiday")
                if self.data:
                    logger.info("Returning cached data")
                    return self.data
                else:
                    logger.info("No cached data available, attempting to fetch data")

            # Clear cache to ensure fresh data
            self.ingestion.stock_data = {}
            self.ingestion.news_data = {}
            self.processor.sentiment_scores = {}

            # Data ingestion
            logger.info(f"Fetching data for {share}")
            raw_data = self.ingestion.get_data(share)
            stock_data = raw_data['stock_data']
            news_data = raw_data['news_data']

            if stock_data.empty or news_data.empty:
                logger.error("Stock or news data is empty")
                return self.data if self.data else None

            # Data processing
            logger.info(f"Processing data for {share}")
            processed_data = self.processor.process_data(share, stock_data, news_data)
            if not processed_data:
                logger.error("Data processing failed")
                return self.data if self.data else None
            stock_data = processed_data['stock_data']
            sentiment_scores = processed_data['sentiment_scores']

            # Latest actual price
            actual_price = stock_data['Close'].iloc[-1] if not stock_data.empty else 0

            # Predict prices for the next 3 days
            logger.info(f"Generating predictions for {share}")
            predictions = self.predictor.get_predictions(stock_data, sentiment_scores, days_ahead=3)
            if not predictions:
                logger.warning("No predictions generated")
                predictions = []

            # Prepare data for charts
            historical_dates = stock_data['Date'].dt.strftime('%Y-%m-%d').tolist()
            historical_prices = stock_data['Close'].tolist()
            prediction_dates = [date.strftime('%Y-%m-%d') for date, _ in predictions] if predictions else []
            predicted_prices = [float(price) for _, price in predictions] if predictions else []

            # Sentiment data for chart
            sentiment_data = {k: v['score'] for k, v in sentiment_scores.items()} if sentiment_scores else {}
            weightage_data = {k: v['weight'] * 100 for k, v in sentiment_scores.items()} if sentiment_scores else {}
            sentiment_sources = list(sentiment_data.keys())
            sentiment_scores_list = list(sentiment_data.values())

            # Scale sentiment scores to price range for combined graph
            price_min, price_max = min(historical_prices) if historical_prices else 0, max(historical_prices) if historical_prices else 0
            sentiment_scaled = [
                ((score + 1) / 2) * (price_max - price_min) + price_min if price_max != price_min else price_min
                for score in sentiment_scores_list
            ] if price_max != price_min else [0] * len(sentiment_scores_list)

            # Align sentiment scores with historical dates
            sentiment_dates = historical_dates
            sentiment_values = []
            for i in range(len(historical_dates)):
                idx = min(i // (len(historical_dates) // len(sentiment_sources) + 1), len(sentiment_sources) - 1) if sentiment_sources else 0
                sentiment_values.append(sentiment_scaled[idx] if sentiment_scaled else 0)

            self.data = {
                'actual_price': float(actual_price),
                'sentiment_data': sentiment_scores,
                'predictions': predictions,
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'chart_data': {
                    'historical': {
                        'dates': historical_dates,
                        'prices': historical_prices
                    },
                    'predictions': {
                        'dates': prediction_dates,
                        'prices': predicted_prices
                    },
                    'sentiment': {
                        'sources': sentiment_sources,
                        'scores': sentiment_scores_list
                    },
                    'weightage': {
                        'sources': list(weightage_data.keys()),
                        'weights': list(weightage_data.values())
                    },
                    'combined': {
                        'dates': historical_dates + prediction_dates,
                        'historical_prices': historical_prices + [None] * len(prediction_dates),
                        'predicted_prices': [None] * len(historical_dates) + predicted_prices,
                        'sentiment_values': sentiment_values + [None] * len(prediction_dates)
                    }
                }
            }
            logger.info(f"Dashboard data prepared with {len(historical_dates)} historical and {len(prediction_dates)} predicted points")
            return self.data
        except Exception as e:
            logger.error(f"Error preparing dashboard data: {e}")
            return self.data if self.data else None

dashboard = Dashboard()

@app.route('/')
def show_dashboard():
    share = 'NIMB'
    data = dashboard.get_dashboard_data(share)
    if not data:
        logger.error("No data available to render dashboard")
        return render_template_string("""
            <!DOCTYPE html>
            <html>
            <head>
                <title>NIMB Share Price Dashboard</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f9; text-align: center; }
                    .error { color: red; font-size: 18px; }
                </style>
            </head>
            <body>
                <h1>NIMB Share Price Dashboard</h1>
                <p class="error">No data available. Please try again later.</p>
                <button onclick="window.location.reload();">Retry</button>
            </body>
            </html>
        """), 503

    # HTML template with Chart.js, combined graph, and enhanced UI
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>NIMB Share Price Dashboard</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body { 
                font-family: 'Segoe UI', Arial, sans-serif; 
                margin: 0; 
                background: linear-gradient(135deg, #f4f4f9 0%, #e0e7ff 100%); 
                color: #333; 
            }
            .header { 
                text-align: center; 
                padding: 20px; 
                background: #ffffff; 
                box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
            }
            .header img { 
                max-width: 100%; 
                height: auto; 
                border-radius: 8px; 
            }
            .container { 
                max-width: 1200px; 
                margin: 20px auto; 
                padding: 0 15px; 
            }
            .section { 
                margin-bottom: 20px; 
                padding: 20px; 
                border-radius: 10px; 
                background: #ffffff; 
                box-shadow: 0 4px 15px rgba(0,0,0,0.1); 
                transition: transform 0.2s; 
            }
            .section:hover { 
                transform: translateY(-5px); 
            }
            h1 { 
                margin: 0; 
                font-size: 2.5em; 
                color: #1a3c34; 
            }
            h2 { 
                color: #2a5d52; 
                font-size: 1.5em; 
                margin-bottom: 15px; 
            }
            table { 
                width: 100%; 
                border-collapse: collapse; 
                margin-top: 10px; 
                background: #f9f9f9; 
            }
            th, td { 
                border: 1px solid #ddd; 
                padding: 12px; 
                text-align: left; 
            }
            th { 
                background: #e0f7fa; 
                font-weight: bold; 
                color: #1a3c34; 
            }
            .controls { 
                text-align: center; 
                margin: 15px 0; 
            }
            .controls button { 
                padding: 10px 20px; 
                margin: 5px; 
                font-size: 14px; 
                background: #4CAF50; 
                color: white; 
                border: none; 
                border-radius: 5px; 
                cursor: pointer; 
                transition: background 0.3s; 
            }
            .controls button:hover { 
                background: #45a049; 
            }
            .controls .disabled { 
                background: #cccccc; 
                cursor: not-allowed; 
            }
            .controls .disabled:hover { 
                background: #cccccc; 
            }
            .refresh { 
                text-align: center; 
                margin-top: 20px; 
            }
            .refresh button { 
                padding: 12px 24px; 
                font-size: 16px; 
                background: #0288d1; 
                color: white; 
                border: none; 
                border-radius: 5px; 
                cursor: pointer; 
                transition: background 0.3s; 
            }
            .refresh button:hover { 
                background: #0277bd; 
            }
            canvas { 
                max-width: 100%; 
                margin-top: 20px; 
                border-radius: 8px; 
                box-shadow: 0 2px 5px rgba(0,0,0,0.1); 
            }
            .loading { 
                text-align: center; 
                font-style: italic; 
                color: #777; 
            }
            .closed-message { 
                text-align: center; 
                color: #888; 
                font-style: italic; 
                margin-bottom: 15px; 
            }
            @media (max-width: 768px) {
                h1 { font-size: 1.8em; }
                h2 { font-size: 1.2em; }
                table, th, td { font-size: 12px; padding: 8px; }
                .section { padding: 15px; }
                .controls button { font-size: 12px; padding: 8px 16px; }
                .refresh button { font-size: 14px; padding: 10px 20px; }
            }
            @media (max-width: 480px) {
                h1 { font-size: 1.5em; }
                h2 { font-size: 1em; }
                table, th, td { font-size: 10px; padding: 6px; }
                .controls button { font-size: 10px; padding: 6px 12px; }
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>NIMB Share Price Dashboard</h1>
            <img src="{{ dashboard.image_url }}" alt="Stock Market Banner" onerror="this.src='https://via.placeholder.com/1350x300?text=Stock+Market+Banner';">
        </div>
        <div class="container">
            {% if not dashboard.is_market_open() %}
            <div class="closed-message">
                Market is closed or it's a holiday (Friday/Saturday). Showing last available data.<br>
                Trading hours: 10:00 AM - 3:45 PM, Sunday-Thursday.
            </div>
            {% endif %}
            <div class="section">
                <h2>Actual Share Price</h2>
                <p>Latest Close Price: Rs {{ actual_price|round(2) }}</p>
                <p>Last Updated: {{ last_updated }}</p>
            </div>
            <div class="section">
                <h2>Sentiment Analysis</h2>
                {% if sentiment_data %}
                <table>
                    <tr>
                        <th>Source</th>
                        <th>Sentiment Score</th>
                        <th>Weightage</th>
                    </tr>
                    {% for source, info in sentiment_data.items() %}
                    <tr>
                        <td>{{ source }}</td>
                        <td>{{ info.score|round(2) }}</td>
                        <td>{{ (info.weight * 100)|round(0) }}%</td>
                    </tr>
                    {% endfor %}
                </table>
                {% else %}
                <p>No sentiment data available.</p>
                {% endif %}
            </div>
            <div class="section">
                <h2>Combined Overview (Price, Sentiment, Predictions)</h2>
                <div class="loading" id="combinedChartLoading">Loading combined chart...</div>
                <canvas id="combinedChart" style="display: block;"></canvas>
            </div>
            <div class="section">
                <h2>Detailed Charts</h2>
                <div class="controls">
                    <button onclick="toggleChart('priceChart', this)">Toggle Price Chart</button>
                    <button onclick="toggleChart('sentimentChart', this)">Toggle Sentiment Chart</button>
                    <button onclick="toggleChart('predictionChart', this)">Toggle Prediction Chart</button>
                    <button id="liveToggle" onclick="toggleLiveUpdate(this)">Toggle Live Update</button>
                </div>
                <div class="loading" id="chartLoading">Loading detailed charts...</div>
                <canvas id="priceChart" style="display: block;"></canvas>
                <canvas id="sentimentChart" style="display: block;"></canvas>
                <canvas id="predictionChart" style="display: block;"></canvas>
            </div>
            <div class="section">
                <h2>Predicted Prices (Next 3 Days)</h2>
                {% if predictions %}
                <table>
                    <tr>
                        <th>Date</th>
                        <th>Predicted Price (Rs)</th>
                    </tr>
                    {% for date, price in predictions %}
                    <tr>
                        <td>{{ date.strftime('%Y-%m-%d') }}</td>
                        <td>{{ price|round(2) }}</td>
                    </tr>
                    {% endfor %}
                </table>
                {% else %}
                <p>No predictions available.</p>
                {% endif %}
            </div>
            <div class="refresh">
                <button id="refreshBtn" onclick="window.location.reload();">Refresh</button>
            </div>
        </div>
        <script>
            let liveUpdateEnabled = false;
            let chartInstances = {};

            document.addEventListener('DOMContentLoaded', function() {
                const chartLoading = document.getElementById('chartLoading');
                const combinedChartLoading = document.getElementById('combinedChartLoading');
                const refreshBtn = document.getElementById('refreshBtn');
                const liveToggle = document.getElementById('liveToggle');
                const isMarketOpen = {{ 'true' if dashboard.is_market_open() else 'false' }};

                if (!isMarketOpen) {
                    refreshBtn.classList.add('disabled');
                    liveToggle.classList.add('disabled');
                }

                chartLoading.style.display = 'none';
                combinedChartLoading.style.display = 'none';

                // Initialize charts
                const chartData = {{ chart_data|tojson }};
                if (!chartData.historical.dates || chartData.historical.dates.length === 0) {
                    chartLoading.textContent = 'No chart data available.';
                    combinedChartLoading.textContent = 'No combined chart data available.';
                    return;
                }

                // Combined Chart
                try {
                    chartInstances['combinedChart'] = new Chart(document.getElementById('combinedChart').getContext('2d'), {
                        type: 'line',
                        data: {
                            labels: chartData.combined.dates,
                            datasets: [
                                {
                                    label: 'Historical Price (Rs)',
                                    data: chartData.combined.historical_prices,
                                    borderColor: 'rgba(75, 192, 192, 1)',
                                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                                    fill: false,
                                    pointRadius: 3,
                                    borderWidth: 2
                                },
                                {
                                    label: 'Predicted Price (Rs)',
                                    data: chartData.combined.predicted_prices,
                                    borderColor: 'rgba(255, 99, 132, 1)',
                                    backgroundColor: 'rgba(255, 99, 132, 0.2)',
                                    fill: false,
                                    pointRadius: 3,
                                    borderWidth: 2,
                                    borderDash: [5, 5]
                                },
                                {
                                    label: 'Scaled Sentiment',
                                    data: chartData.combined.sentiment_values,
                                    borderColor: 'rgba(255, 159, 64, 1)',
                                    backgroundColor: 'rgba(255, 159, 64, 0.2)',
                                    fill: false,
                                    pointRadius: 3,
                                    borderWidth: 2,
                                    borderDash: [3, 3]
                                }
                            ]
                        },
                        options: {
                            scales: {
                                x: { title: { display: true, text: 'Date' } },
                                y: { title: { display: true, text: 'Price / Scaled Sentiment (Rs)' }, beginAtZero: false }
                            },
                            plugins: { legend: { display: true }, tooltip: { enabled: true } },
                            responsive: true,
                            maintainAspectRatio: false
                        }
                    });
                } catch (error) {
                    console.error('Error rendering combined chart:', error);
                    combinedChartLoading.textContent = 'Error loading combined chart.';
                }

                // Price Chart
                try {
                    chartInstances['priceChart'] = new Chart(document.getElementById('priceChart').getContext('2d'), {
                        type: 'line',
                        data: {
                            labels: chartData.historical.dates,
                            datasets: [{
                                label: 'Historical Price (Rs)',
                                data: chartData.historical.prices,
                                borderColor: 'rgba(75, 192, 192, 1)',
                                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                                fill: false,
                                pointRadius: 3,
                                borderWidth: 2
                            }]
                        },
                        options: {
                            scales: { x: { title: { display: true, text: 'Date' } }, y: { title: { display: true, text: 'Price (Rs)' }, beginAtZero: false } },
                            plugins: { legend: { display: true }, tooltip: { enabled: true } },
                            responsive: true,
                            maintainAspectRatio: false
                        }
                    });
                } catch (error) {
                    console.error('Error rendering price chart:', error);
                    chartLoading.textContent = 'Error loading detailed charts.';
                }

                // Sentiment Chart
                try {
                    chartInstances['sentimentChart'] = new Chart(document.getElementById('sentimentChart').getContext('2d'), {
                        type: 'bar',
                        data: {
                            labels: chartData.sentiment.sources,
                            datasets: [{
                                label: 'Sentiment Score',
                                data: chartData.sentiment.scores,
                                backgroundColor: 'rgba(54, 162, 235, 0.6)',
                                borderColor: 'rgba(54, 162, 235, 1)',
                                borderWidth: 1
                            }]
                        },
                        options: {
                            scales: { y: { title: { display: true, text: 'Sentiment Score' }, beginAtZero: true, max: 1 } },
                            plugins: { legend: { display: true }, tooltip: { enabled: true } },
                            responsive: true,
                            maintainAspectRatio: false
                        }
                    });
                } catch (error) {
                    console.error('Error rendering sentiment chart:', error);
                    chartLoading.textContent = 'Error loading detailed charts.';
                }

                // Prediction Chart
                try {
                    chartInstances['predictionChart'] = new Chart(document.getElementById('predictionChart').getContext('2d'), {
                        type: 'line',
                        data: {
                            labels: chartData.predictions.dates,
                            datasets: [{
                                label: 'Predicted Price (Rs)',
                                data: chartData.predictions.prices,
                                borderColor: 'rgba(255, 99, 132, 1)',
                                backgroundColor: 'rgba(255, 99, 132, 0.2)',
                                fill: false,
                                pointRadius: 3,
                                borderWidth: 2,
                                borderDash: [5, 5]
                            }]
                        },
                        options: {
                            scales: { x: { title: { display: true, text: 'Date' } }, y: { title: { display: true, text: 'Price (Rs)' }, beginAtZero: false } },
                            plugins: { legend: { display: true }, tooltip: { enabled: true } },
                            responsive: true,
                            maintainAspectRatio: false
                        }
                    });
                } catch (error) {
                    console.error('Error rendering prediction chart:', error);
                    chartLoading.textContent = 'Error loading detailed charts.';
                }

                function toggleChart(chartId, button) {
                    const chart = document.getElementById(chartId);
                    const isVisible = chart.style.display === 'block';
                    chart.style.display = isVisible ? 'none' : 'block';
                    button.textContent = isVisible ? 'Show ' + chartId.replace('Chart', '') + ' Chart' : 'Hide ' + chartId.replace('Chart', '') + ' Chart';
                }

                function toggleLiveUpdate(button) {
                    if (!isMarketOpen) {
                        alert('Live updates are only available during market hours (10:00 AM - 3:45 PM, Sunday-Thursday).');
                        return;
                    }
                    liveUpdateEnabled = !liveUpdateEnabled;
                    button.textContent = liveUpdateEnabled ? 'Disable Live Update' : 'Enable Live Update';
                    if (liveUpdateEnabled) {
                        setInterval(() => {
                            if (liveUpdateEnabled && isMarketOpen) window.location.reload();
                        }, 60000); // Refresh every minute
                    }
                }

                // Handle page reload on refresh button click
                refreshBtn.addEventListener('click', function() {
                    if (this.classList.contains('disabled')) {
                        alert('Refresh is disabled outside market hours (10:00 AM - 3:45 PM, Sunday-Thursday).');
                    } else {
                        window.location.reload();
                    }
                });
            });
        </script>
    </body>
    </html>
    """
    return render_template_string(html_template, data=data, dashboard=dashboard)

if __name__ == "__main__":
    app.run(debug=True, port=5000)