"""
TerraNeuron Pipeline Simulation Script
QA Engineer Test Tool for End-to-End Verification with HTML Report

This script generates realistic sensor data and sends it to terra-sense,
verifying the complete data flow through the microservices pipeline:
terra-sense → Kafka → terra-cortex (Hybrid AI) → Kafka → terra-ops

Features:
- Local AI (Ollama) integration verification
- Professional HTML test report generation
- AI recommendation tracking and highlighting
- Performance metrics (latency, success rate)

Usage:
    python tests/simulation.py
    python tests/simulation.py --interval 2 --count 50
    python tests/simulation.py --mode anomaly --verbose
    python tests/simulation.py --mode anomaly --count 20 --report
"""

import argparse
import random
import time
import sys
import json
from datetime import datetime
from typing import Dict, Any, Literal, List, Optional
from pathlib import Path

try:
    import requests
except ImportError:
    print("❌ Error: 'requests' library not found.")
    print("   Install it with: pip install requests")
    sys.exit(1)


class SensorSimulator:
    """Simulates smart farm sensor data generation"""
    
    def __init__(self, mode: Literal["normal", "anomaly", "mixed"] = "normal"):
        self.mode = mode
        self.sensor_types = ["temperature", "humidity", "soilMoisture", "co2", "light"]
        self.farm_ids = [
            "sensor_temp_001",
            "sensor_hum_001", 
            "sensor_soil_001",
            "sensor_co2_001",
            "sensor_light_001"
        ]
        
        # Normal ranges for each sensor type
        self.normal_ranges = {
            "temperature": (15.0, 30.0),    # °C
            "humidity": (40.0, 80.0),       # %
            "soilMoisture": (30.0, 70.0),   # %
            "co2": (300.0, 1000.0),         # ppm
            "light": (100.0, 800.0)         # lux
        }
        
        # Anomaly ranges (values outside normal)
        self.anomaly_ranges = {
            "temperature": (35.0, 45.0),    # Too hot
            "humidity": (10.0, 30.0),       # Too dry
            "soilMoisture": (5.0, 20.0),    # Too dry
            "co2": (1500.0, 2500.0),        # Too high
            "light": (50.0, 90.0)           # Too dark
        }
        
    def generate_sensor_data(self) -> Dict[str, Any]:
        """Generate a single sensor data point matching Terra-Sense SensorData model"""
        sensor_type = random.choice(self.sensor_types)
        sensor_id = random.choice(self.farm_ids)
        
        # Determine if this should be anomaly based on mode
        is_anomaly = self._should_generate_anomaly()
        
        # Generate value
        if is_anomaly:
            min_val, max_val = self.anomaly_ranges[sensor_type]
        else:
            min_val, max_val = self.normal_ranges[sensor_type]
        
        value = round(random.uniform(min_val, max_val), 2)
        
        return {
            "sensorId": sensor_id,
            "sensorType": sensor_type,
            "value": value,
            "unit": self._get_unit(sensor_type),
            "farmId": f"farm-{random.choice(['A', 'B', 'C', 'D', 'E'])}",
            "timestamp": datetime.utcnow().isoformat(timespec='milliseconds') + "Z"
        }
    
    def _should_generate_anomaly(self) -> bool:
        """Determine if current data should be anomaly"""
        if self.mode == "normal":
            return False
        elif self.mode == "anomaly":
            return True
        else:  # mixed
            return random.random() < 0.2  # 20% anomaly rate
    
    def _get_unit(self, sensor_type: str) -> str:
        """Get unit for sensor type"""
        units = {
            "temperature": "°C",
            "humidity": "%",
            "soilMoisture": "%",
            "co2": "ppm",
            "light": "lux"
        }
        return units.get(sensor_type, "")


class TestResult:
    """Represents a single test result"""
    def __init__(self, timestamp: str, sensor_data: Dict[str, Any], 
                 status_code: int, response_time: float, 
                 ai_status: str = "UNKNOWN", ai_recommendation: Optional[str] = None,
                 farm_id: str = "", success: bool = True):
        self.timestamp = timestamp
        self.sensor_type = sensor_data.get("sensorType", "")
        self.sensor_value = sensor_data.get("value", 0)
        self.sensor_unit = sensor_data.get("unit", "")
        self.farm_id = farm_id or sensor_data.get("farmId", "")
        self.status_code = status_code
        self.response_time = response_time
        self.ai_status = ai_status
        self.ai_recommendation = ai_recommendation
        self.success = success


class TestReporter:
    """Generates professional HTML test reports"""
    
    def __init__(self):
        self.test_results: List[TestResult] = []
        self.start_time = datetime.now()
        self.end_time = None
    
    def add_result(self, result: TestResult):
        """Add a test result"""
        self.test_results.append(result)
    
    def finalize(self):
        """Mark the end time"""
        self.end_time = datetime.now()
    
    def generate_html_report(self, output_path: Optional[str] = None) -> str:
        """Generate HTML test report"""
        if self.end_time is None:
            self.finalize()
        
        # Calculate statistics
        total_tests = len(self.test_results)
        successful_tests = sum(1 for r in self.test_results if r.success)
        failed_tests = total_tests - successful_tests
        success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0
        
        ai_triggered_count = sum(1 for r in self.test_results if r.ai_status == "ANOMALY")
        ai_recommendations_count = sum(1 for r in self.test_results if r.ai_recommendation)
        
        avg_latency = sum(r.response_time for r in self.test_results) / total_tests if total_tests > 0 else 0
        
        duration = (self.end_time - self.start_time).total_seconds()
        
        # Generate filename if not provided
        if output_path is None:
            timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
            output_path = f"test_report_{timestamp}.html"
        
        # Generate HTML
        html_content = self._generate_html(
            total_tests=total_tests,
            successful_tests=successful_tests,
            failed_tests=failed_tests,
            success_rate=success_rate,
            ai_triggered_count=ai_triggered_count,
            ai_recommendations_count=ai_recommendations_count,
            avg_latency=avg_latency,
            duration=duration
        )
        
        # Write to file
        output_file = Path(output_path)
        output_file.write_text(html_content, encoding='utf-8')
        
        return str(output_file.absolute())
    
    def _generate_html(self, total_tests: int, successful_tests: int, failed_tests: int,
                      success_rate: float, ai_triggered_count: int, ai_recommendations_count: int,
                      avg_latency: float, duration: float) -> str:
        """Generate HTML content"""
        
        # Generate table rows
        table_rows = ""
        for idx, result in enumerate(self.test_results, 1):
            row_class = "anomaly-row" if result.ai_status == "ANOMALY" else "normal-row"
            status_badge = f'<span class="badge badge-{result.ai_status.lower()}">{result.ai_status}</span>'
            
            ai_rec_cell = ""
            if result.ai_recommendation:
                ai_rec_cell = f'<span class="ai-recommendation">🤖 {result.ai_recommendation}</span>'
            else:
                ai_rec_cell = '<span class="no-ai">—</span>'
            
            result_badge = '<span class="badge badge-pass">PASS</span>' if result.success else '<span class="badge badge-fail">FAIL</span>'
            
            table_rows += f"""
                <tr class="{row_class}">
                    <td>{idx}</td>
                    <td>{result.timestamp}</td>
                    <td>{result.farm_id}</td>
                    <td>{result.sensor_type}</td>
                    <td>{result.sensor_value} {result.sensor_unit}</td>
                    <td>{status_badge}</td>
                    <td class="ai-recommendation-cell">{ai_rec_cell}</td>
                    <td>{result.response_time:.0f}ms</td>
                    <td>{result_badge}</td>
                </tr>
            """
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TerraNeuron Test Report - {self.start_time.strftime("%Y-%m-%d %H:%M:%S")}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            color: #333;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #2d3748 0%, #1a202c 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        
        .header .subtitle {{
            font-size: 1.2em;
            opacity: 0.9;
        }}
        
        .dashboard {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f7fafc;
        }}
        
        .metric-card {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            text-align: center;
            transition: transform 0.2s;
        }}
        
        .metric-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 4px 16px rgba(0,0,0,0.15);
        }}
        
        .metric-card .value {{
            font-size: 2.5em;
            font-weight: bold;
            margin: 10px 0;
        }}
        
        .metric-card .label {{
            color: #718096;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .metric-card.success .value {{ color: #38a169; }}
        .metric-card.danger .value {{ color: #e53e3e; }}
        .metric-card.warning .value {{ color: #dd6b20; }}
        .metric-card.info .value {{ color: #3182ce; }}
        .metric-card.ai .value {{ color: #805ad5; }}
        
        .table-container {{
            padding: 30px;
            overflow-x: auto;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
        }}
        
        thead {{
            background: linear-gradient(135deg, #4299e1 0%, #3182ce 100%);
            color: white;
        }}
        
        th {{
            padding: 15px;
            text-align: left;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.85em;
            letter-spacing: 1px;
        }}
        
        td {{
            padding: 12px 15px;
            border-bottom: 1px solid #e2e8f0;
        }}
        
        tr.normal-row {{
            background: #f0fff4;
        }}
        
        tr.anomaly-row {{
            background: #fff5f5;
        }}
        
        tr:hover {{
            background: #edf2f7;
        }}
        
        .badge {{
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
            text-transform: uppercase;
        }}
        
        .badge-normal {{
            background: #c6f6d5;
            color: #22543d;
        }}
        
        .badge-anomaly {{
            background: #fed7d7;
            color: #742a2a;
        }}
        
        .badge-unknown {{
            background: #e2e8f0;
            color: #4a5568;
        }}
        
        .badge-pass {{
            background: #9ae6b4;
            color: #22543d;
        }}
        
        .badge-fail {{
            background: #fc8181;
            color: #742a2a;
        }}
        
        .ai-recommendation {{
            display: block;
            background: linear-gradient(135deg, #d6bcfa 0%, #b794f4 100%);
            color: #44337a;
            padding: 10px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 0.95em;
            line-height: 1.4;
            box-shadow: 0 2px 8px rgba(128, 90, 213, 0.3);
        }}
        
        .ai-recommendation-cell {{
            max-width: 400px;
        }}
        
        .no-ai {{
            color: #cbd5e0;
            font-size: 1.2em;
        }}
        
        .footer {{
            background: #2d3748;
            color: white;
            padding: 20px;
            text-align: center;
            font-size: 0.9em;
        }}
        
        .highlight-box {{
            background: #fefcbf;
            border-left: 4px solid #ecc94b;
            padding: 15px;
            margin: 20px 30px;
            border-radius: 4px;
        }}
        
        .highlight-box strong {{
            color: #744210;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌾 TerraNeuron Test Report 🧠</h1>
            <p class="subtitle">Hybrid AI Pipeline Verification | Local AI (Ollama) Integration Test</p>
            <p style="margin-top: 10px; opacity: 0.8;">
                Test Date: {self.start_time.strftime("%Y-%m-%d %H:%M:%S")} | 
                Duration: {duration:.2f}s
            </p>
        </div>
        
        <div class="highlight-box">
            <strong>🤖 Local AI Verification:</strong> This report tracks AI-generated recommendations from the Hybrid AI Architecture (Local Edge Analyzer + Cloud/Local LLM). 
            AI recommendations are highlighted in <span style="background: #d6bcfa; padding: 2px 6px; border-radius: 3px;">purple</span> below.
        </div>
        
        <div class="dashboard">
            <div class="metric-card info">
                <div class="label">Total Tests</div>
                <div class="value">{total_tests}</div>
            </div>
            
            <div class="metric-card success">
                <div class="label">Success Rate</div>
                <div class="value">{success_rate:.1f}%</div>
            </div>
            
            <div class="metric-card warning">
                <div class="label">AI Triggered</div>
                <div class="value">{ai_triggered_count}</div>
                <div class="label" style="margin-top: 5px; font-size: 0.75em;">Anomalies Detected</div>
            </div>
            
            <div class="metric-card ai">
                <div class="label">AI Recommendations</div>
                <div class="value">{ai_recommendations_count}</div>
                <div class="label" style="margin-top: 5px; font-size: 0.75em;">LLM Responses</div>
            </div>
            
            <div class="metric-card success">
                <div class="label">Passed</div>
                <div class="value">{successful_tests}</div>
            </div>
            
            <div class="metric-card danger">
                <div class="label">Failed</div>
                <div class="value">{failed_tests}</div>
            </div>
            
            <div class="metric-card info">
                <div class="label">Avg Latency</div>
                <div class="value">{avg_latency:.0f}ms</div>
            </div>
        </div>
        
        <div class="table-container">
            <h2 style="margin-bottom: 20px; color: #2d3748;">📋 Detailed Test Results</h2>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Timestamp</th>
                        <th>Farm ID</th>
                        <th>Sensor Type</th>
                        <th>Value</th>
                        <th>AI Status</th>
                        <th>🤖 AI Recommendation</th>
                        <th>Latency</th>
                        <th>Result</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            <p>Generated by TerraNeuron Simulation Tool</p>
            <p style="margin-top: 5px; opacity: 0.8;">Smart Farm Microservices Pipeline | Hybrid AI Architecture</p>
        </div>
    </div>
</body>
</html>
"""
        return html


class PipelineTester:
    """Tests the TerraNeuron pipeline end-to-end with AI verification"""
    
    def __init__(self, terra_sense_url: str = "http://localhost:8081", 
                 terra_ops_url: str = "http://localhost:8080",
                 verbose: bool = False):
        self.terra_sense_url = terra_sense_url
        self.terra_ops_url = terra_ops_url
        self.ingest_endpoint = f"{terra_sense_url}/api/v1/ingest/sensor-data"
        self.health_endpoint = f"{terra_sense_url}/api/v1/health"
        self.insights_endpoint = f"{terra_ops_url}/api/v1/dashboard/insights"
        self.verbose = verbose
        
        # Statistics
        self.total_sent = 0
        self.total_success = 0
        self.total_failed = 0
        self.status_codes = {}
        
        # For AI verification
        self.sent_data_timestamps = []
    
    def check_terra_sense_health(self) -> bool:
        """Check if terra-sense service is healthy"""
        try:
            response = requests.get(self.health_endpoint, timeout=5)
            if response.status_code == 200:
                print(f"✅ terra-sense is healthy (Status: {response.status_code})")
                return True
            else:
                print(f"⚠️  terra-sense returned status {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            print(f"❌ Cannot connect to terra-sense at {self.terra_sense_url}")
            print("   Make sure Docker Compose is running: docker-compose up -d")
            return False
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            return False
    
    def send_sensor_data(self, data: Dict[str, Any]) -> tuple[requests.Response, float]:
        """Send sensor data to terra-sense ingestion endpoint, returns (response, latency_ms)"""
        try:
            start_time = time.time()
            response = requests.post(
                self.ingest_endpoint,
                json=data,
                timeout=5
            )
            latency_ms = (time.time() - start_time) * 1000
            
            # Track timestamp for later insights query
            self.sent_data_timestamps.append(data['timestamp'])
            
            # Update statistics
            self.total_sent += 1
            status_code = response.status_code
            self.status_codes[status_code] = self.status_codes.get(status_code, 0) + 1
            
            if 200 <= status_code < 300:
                self.total_success += 1
            else:
                self.total_failed += 1
            
            return response, latency_ms
            
        except requests.exceptions.Timeout:
            self.total_sent += 1
            self.total_failed += 1
            self.status_codes['timeout'] = self.status_codes.get('timeout', 0) + 1
            raise
        except Exception as e:
            self.total_sent += 1
            self.total_failed += 1
            self.status_codes['error'] = self.status_codes.get('error', 0) + 1
            raise
    
    def query_insights(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Query terra-ops for recent insights with AI recommendations"""
        try:
            response = requests.get(
                self.insights_endpoint,
                params={"limit": limit},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                # Handle different response formats
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and 'insights' in data:
                    return data['insights']
                elif isinstance(data, dict) and 'data' in data:
                    return data['data']
                else:
                    return []
            else:
                if self.verbose:
                    print(f"⚠️  Failed to query insights: HTTP {response.status_code}")
                return []
                
        except Exception as e:
            if self.verbose:
                print(f"⚠️  Error querying insights: {e}")
            return []
    
    def find_insight_for_data(self, sensor_data: Dict[str, Any], insights: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Find the insight that matches the sensor data"""
        farm_id = sensor_data.get('farmId', '')
        timestamp = sensor_data.get('timestamp', '')
        
        # Look for insights with matching farm_id and close timestamp
        for insight in insights:
            insight_farm = insight.get('farmId', insight.get('farm_id', ''))
            if insight_farm == farm_id:
                # Found a match for this farm (good enough for testing)
                return insight
        
        return None
    
    def print_statistics(self):
        """Print test statistics"""
        print("\n" + "="*60)
        print("📊 TEST STATISTICS")
        print("="*60)
        print(f"Total Requests:   {self.total_sent}")
        print(f"✅ Success:        {self.total_success} ({self._percentage(self.total_success, self.total_sent)}%)")
        print(f"❌ Failed:         {self.total_failed} ({self._percentage(self.total_failed, self.total_sent)}%)")
        print("\nStatus Code Distribution:")
        for code, count in sorted(self.status_codes.items()):
            print(f"  {code}: {count} ({self._percentage(count, self.total_sent)}%)")
        print("="*60)
    
    def _percentage(self, part: int, total: int) -> str:
        """Calculate percentage"""
        if total == 0:
            return "0.00"
        return f"{(part / total * 100):.2f}"


def print_banner():
    """Print simulation banner"""
    banner = """
╔═══════════════════════════════════════════════════════════╗
║   🌾 TerraNeuron Pipeline Simulation Tool 🧠              ║
║   End-to-End Testing for Smart Farm Microservices        ║
╚═══════════════════════════════════════════════════════════╝
"""
    print(banner)


def main():
    """Main simulation loop"""
    parser = argparse.ArgumentParser(
        description="TerraNeuron Pipeline Simulation Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Normal mode, 10 requests, 1 second interval
  python tests/simulation.py
  
  # Anomaly mode, 20 requests, 2 second interval
  python tests/simulation.py --mode anomaly --count 20 --interval 2
  
  # Mixed mode (80% normal, 20% anomaly), verbose output
  python tests/simulation.py --mode mixed --count 50 --verbose
  
  # Custom terra-sense URL
  python tests/simulation.py --url http://192.168.1.100:8081
        """
    )
    
    parser.add_argument(
        "--mode",
        choices=["normal", "anomaly", "mixed"],
        default="mixed",
        help="Data generation mode (default: mixed)"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of sensor data points to send (default: 10)"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Interval between requests in seconds (default: 1.0)"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8081",
        help="terra-sense service URL (default: http://localhost:8081)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output (show full request/response)"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate HTML test report (recommended for AI verification)"
    )
    parser.add_argument(
        "--wait-for-insights",
        type=int,
        default=3,
        help="Seconds to wait before querying insights (default: 3)"
    )
    
    args = parser.parse_args()
    
    # Print banner
    print_banner()
    
    # Initialize simulator, tester, and reporter
    simulator = SensorSimulator(mode=args.mode)
    tester = PipelineTester(terra_sense_url=args.url, verbose=args.verbose)
    reporter = TestReporter() if args.report else None
    
    # Configuration summary
    print(f"📋 Configuration:")
    print(f"   Mode:           {args.mode}")
    print(f"   Count:          {args.count} requests")
    print(f"   Interval:       {args.interval} seconds")
    print(f"   Target URL:     {args.url}")
    print(f"   Verbose:        {args.verbose}")
    print(f"   HTML Report:    {args.report}")
    if args.report:
        print(f"   Insight Wait:   {args.wait_for_insights}s")
    print()
    
    # Health check
    print("🔍 Checking terra-sense health...")
    if not tester.check_terra_sense_health():
        print("\n⚠️  Warning: terra-sense health check failed. Continuing anyway...")
    print()
    
    # Main simulation loop
    print(f"🚀 Starting simulation: Sending {args.count} sensor data points...")
    print("-" * 60)
    
    sent_sensor_data = []  # Store for later AI verification
    
    try:
        for i in range(args.count):
            # Generate sensor data
            sensor_data = simulator.generate_sensor_data()
            sent_sensor_data.append(sensor_data)
            
            # Send to terra-sense
            try:
                response, latency_ms = tester.send_sensor_data(sensor_data)
                
                # Print result
                status_icon = "✅" if 200 <= response.status_code < 300 else "❌"
                print(f"{status_icon} [{i+1}/{args.count}] "
                      f"{sensor_data['sensorType']:15s} = {sensor_data['value']:7.2f} {sensor_data['unit']:5s} "
                      f"| HTTP {response.status_code} | {latency_ms:.0f}ms")
                
                if args.verbose:
                    print(f"   Request:  {sensor_data}")
                    print(f"   Response: {response.text}")
                    print()
                
                # Store test result (without AI status yet)
                if reporter:
                    result = TestResult(
                        timestamp=datetime.now().strftime("%H:%M:%S.%f")[:-3],
                        sensor_data=sensor_data,
                        status_code=response.status_code,
                        response_time=latency_ms,
                        success=(200 <= response.status_code < 300)
                    )
                    reporter.add_result(result)
                
            except requests.exceptions.Timeout:
                print(f"⏱️  [{i+1}/{args.count}] Request timeout")
                if reporter:
                    result = TestResult(
                        timestamp=datetime.now().strftime("%H:%M:%S.%f")[:-3],
                        sensor_data=sensor_data,
                        status_code=0,
                        response_time=5000,
                        success=False
                    )
                    reporter.add_result(result)
            except Exception as e:
                print(f"❌ [{i+1}/{args.count}] Error: {e}")
                if reporter:
                    result = TestResult(
                        timestamp=datetime.now().strftime("%H:%M:%S.%f")[:-3],
                        sensor_data=sensor_data,
                        status_code=0,
                        response_time=0,
                        success=False
                    )
                    reporter.add_result(result)
            
            # Wait before next request (except for last iteration)
            if i < args.count - 1:
                time.sleep(args.interval)
        
        print("-" * 60)
        print("✅ Simulation completed!")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Simulation interrupted by user (Ctrl+C)")
    
    # Print statistics
    tester.print_statistics()
    
    # AI Verification: Query insights from terra-ops
    if args.report:
        print(f"\n🤖 Verifying AI Integration...")
        print(f"   Waiting {args.wait_for_insights}s for pipeline processing...")
        time.sleep(args.wait_for_insights)
        
        print(f"   Querying terra-ops for insights...")
        insights = tester.query_insights(limit=args.count * 2)
        
        if insights:
            print(f"   ✅ Retrieved {len(insights)} insights from terra-ops")
            
            # Match insights to sent data and update AI status
            ai_recommendations_found = 0
            for i, result in enumerate(reporter.test_results):
                if i < len(sent_sensor_data):
                    insight = tester.find_insight_for_data(sent_sensor_data[i], insights)
                    if insight:
                        # Update AI status
                        result.ai_status = insight.get('status', 'UNKNOWN')
                        
                        # Check for LLM recommendation
                        llm_rec = insight.get('llmRecommendation', insight.get('llm_recommendation'))
                        if llm_rec:
                            result.ai_recommendation = llm_rec
                            ai_recommendations_found += 1
            
            print(f"   🧠 AI Recommendations found: {ai_recommendations_found}/{len(reporter.test_results)}")
            
        else:
            print(f"   ⚠️  No insights retrieved from terra-ops")
            print(f"      This may be normal if no anomalies were detected")
        
        # Generate HTML report
        print(f"\n📝 Generating HTML test report...")
        report_path = reporter.generate_html_report()
        print(f"   ✅ Report saved to: {report_path}")
        print(f"   📂 Open in browser: file:///{report_path}")
    
    # Next steps
    print("\n📌 Next Steps:")
    print("   1. Check terra-sense logs:   docker-compose logs -f terra-sense")
    print("   2. Check terra-cortex logs:  docker-compose logs -f terra-cortex")
    print("   3. Check terra-ops logs:     docker-compose logs -f terra-ops")
    if not args.report:
        print("   4. Generate HTML report:     python tests/simulation.py --mode anomaly --count 20 --report")
    print()


if __name__ == "__main__":
    main()
