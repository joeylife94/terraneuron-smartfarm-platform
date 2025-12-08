"""
TerraNeuron Pipeline Simulation Script
QA Engineer Test Tool for End-to-End Verification

This script generates realistic sensor data and sends it to terra-sense,
verifying the complete data flow through the microservices pipeline:
terra-sense → Kafka → terra-cortex → Kafka → terra-ops

Usage:
    python tests/simulation.py
    python tests/simulation.py --interval 2 --count 50
    python tests/simulation.py --mode anomaly --verbose
"""

import argparse
import random
import time
import sys
from datetime import datetime
from typing import Dict, Any, Literal

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


class PipelineTester:
    """Tests the TerraNeuron pipeline end-to-end"""
    
    def __init__(self, terra_sense_url: str = "http://localhost:8081", verbose: bool = False):
        self.terra_sense_url = terra_sense_url
        self.ingest_endpoint = f"{terra_sense_url}/api/v1/ingest/sensor-data"
        self.health_endpoint = f"{terra_sense_url}/api/v1/health"
        self.verbose = verbose
        
        # Statistics
        self.total_sent = 0
        self.total_success = 0
        self.total_failed = 0
        self.status_codes = {}
    
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
    
    def send_sensor_data(self, data: Dict[str, Any]) -> requests.Response:
        """Send sensor data to terra-sense ingestion endpoint"""
        try:
            response = requests.post(
                self.ingest_endpoint,
                json=data,
                timeout=5
            )
            
            # Update statistics
            self.total_sent += 1
            status_code = response.status_code
            self.status_codes[status_code] = self.status_codes.get(status_code, 0) + 1
            
            if 200 <= status_code < 300:
                self.total_success += 1
            else:
                self.total_failed += 1
            
            return response
            
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
    
    args = parser.parse_args()
    
    # Print banner
    print_banner()
    
    # Initialize simulator and tester
    simulator = SensorSimulator(mode=args.mode)
    tester = PipelineTester(terra_sense_url=args.url, verbose=args.verbose)
    
    # Configuration summary
    print(f"📋 Configuration:")
    print(f"   Mode:           {args.mode}")
    print(f"   Count:          {args.count} requests")
    print(f"   Interval:       {args.interval} seconds")
    print(f"   Target URL:     {args.url}")
    print(f"   Verbose:        {args.verbose}")
    print()
    
    # Health check
    print("🔍 Checking terra-sense health...")
    if not tester.check_terra_sense_health():
        print("\n⚠️  Warning: terra-sense health check failed. Continuing anyway...")
    print()
    
    # Main simulation loop
    print(f"🚀 Starting simulation: Sending {args.count} sensor data points...")
    print("-" * 60)
    
    try:
        for i in range(args.count):
            # Generate sensor data
            sensor_data = simulator.generate_sensor_data()
            
            # Send to terra-sense
            try:
                response = tester.send_sensor_data(sensor_data)
                
                # Print result
                status_icon = "✅" if 200 <= response.status_code < 300 else "❌"
                print(f"{status_icon} [{i+1}/{args.count}] "
                      f"{sensor_data['sensorType']:15s} = {sensor_data['value']:7.2f} {sensor_data['unit']:5s} "
                      f"| HTTP {response.status_code}")
                
                if args.verbose:
                    print(f"   Request:  {sensor_data}")
                    print(f"   Response: {response.text}")
                    print()
                
            except requests.exceptions.Timeout:
                print(f"⏱️  [{i+1}/{args.count}] Request timeout")
            except Exception as e:
                print(f"❌ [{i+1}/{args.count}] Error: {e}")
            
            # Wait before next request (except for last iteration)
            if i < args.count - 1:
                time.sleep(args.interval)
        
        print("-" * 60)
        print("✅ Simulation completed!")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Simulation interrupted by user (Ctrl+C)")
    
    # Print statistics
    tester.print_statistics()
    
    # Next steps
    print("\n📌 Next Steps:")
    print("   1. Check terra-sense logs:   docker-compose logs -f terra-sense")
    print("   2. Check terra-cortex logs:  docker-compose logs -f terra-cortex")
    print("   3. Check terra-ops logs:     docker-compose logs -f terra-ops")
    print("   4. View insights in MySQL:   docker exec -it mysql mysql -u terra -pterra2025 -e 'SELECT * FROM terra_db.insights ORDER BY timestamp DESC LIMIT 10'")
    print("   5. Query dashboard API:      curl http://localhost:8083/api/v1/dashboard/insights")
    print()


if __name__ == "__main__":
    main()
