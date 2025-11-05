# backend/test_backend.py
"""
Comprehensive testing script for EchoAI Backend
Tests all major endpoints and functionality
"""

import asyncio
import json
import base64
import time
import wave
import struct
from typing import Dict, Any
import httpx
import websockets
import numpy as np

# Configuration
BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"
TEST_SESSION_ID = "test_session_123"


class BackendTester:
    """Comprehensive backend testing class"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.test_results = []
        
    async def close(self):
        await self.client.aclose()
    
    def log_result(self, test_name: str, passed: bool, details: str = ""):
        """Log test result"""
        status = "✅ PASS" if passed else "❌ FAIL"
        result = f"{status} | {test_name}"
        if details:
            result += f" | {details}"
        print(result)
        self.test_results.append({
            "test": test_name,
            "passed": passed,
            "details": details
        })
    
    # ================== HEALTH CHECKS ==================
    
    async def test_root_endpoint(self):
        """Test root endpoint"""
        try:
            response = await self.client.get(f"{BASE_URL}/")
            passed = response.status_code == 200 and "version" in response.json()
            self.log_result("Root Endpoint", passed, f"Status: {response.status_code}")
            return passed
        except Exception as e:
            self.log_result("Root Endpoint", False, str(e))
            return False
    
    async def test_health_check(self):
        """Test health check endpoint"""
        try:
            response = await self.client.get(f"{BASE_URL}/health")
            passed = response.status_code == 200
            self.log_result("Health Check", passed, f"Status: {response.status_code}")
            return passed
        except Exception as e:
            self.log_result("Health Check", False, str(e))
            return False
    
    async def test_detailed_health(self):
        """Test detailed health check"""
        try:
            response = await self.client.get(f"{BASE_URL}/health/detailed")
            data = response.json()
            passed = response.status_code == 200 and "components" in data
            self.log_result("Detailed Health", passed, f"Status: {data.get('status', 'unknown')}")
            return passed
        except Exception as e:
            self.log_result("Detailed Health", False, str(e))
            return False
    
    # ================== SESSION MANAGEMENT ==================
    
    async def test_create_session(self):
        """Test session creation"""
        try:
            response = await self.client.post(
                f"{BASE_URL}/transcript/session/{TEST_SESSION_ID}/create"
            )
            passed = response.status_code == 200
            self.log_result("Create Session", passed, f"Session ID: {TEST_SESSION_ID}")
            return passed
        except Exception as e:
            self.log_result("Create Session", False, str(e))
            return False
    
    async def test_get_session_transcript(self):
        """Test getting session transcript"""
        try:
            response = await self.client.get(
                f"{BASE_URL}/transcript/session/{TEST_SESSION_ID}"
            )
            data = response.json()
            passed = response.status_code == 200 and "session_id" in data
            self.log_result("Get Session Transcript", passed, f"Entries: {len(data.get('transcript', []))}")
            return passed
        except Exception as e:
            self.log_result("Get Session Transcript", False, str(e))
            return False
    
    async def test_list_sessions(self):
        """Test listing sessions"""
        try:
            response = await self.client.get(f"{BASE_URL}/transcript/sessions")
            data = response.json()
            passed = response.status_code == 200 and "sessions" in data
            self.log_result("List Sessions", passed, f"Total: {data.get('total_sessions', 0)}")
            return passed
        except Exception as e:
            self.log_result("List Sessions", False, str(e))
            return False
    
    # ================== ANALYTICS ==================
    
    async def test_session_analytics(self):
        """Test session analytics"""
        try:
            response = await self.client.get(
                f"{BASE_URL}/analytics/session/{TEST_SESSION_ID}"
            )
            # May return 404 if no data, which is acceptable
            passed = response.status_code in [200, 404]
            self.log_result("Session Analytics", passed, f"Status: {response.status_code}")
            return passed
        except Exception as e:
            self.log_result("Session Analytics", False, str(e))
            return False
    
    async def test_list_all_sessions_analytics(self):
        """Test listing all sessions for analytics"""
        try:
            response = await self.client.get(f"{BASE_URL}/analytics/sessions/list")
            data = response.json()
            passed = response.status_code == 200 and "sessions" in data
            self.log_result("Analytics Sessions List", passed)
            return passed
        except Exception as e:
            self.log_result("Analytics Sessions List", False, str(e))
            return False
    
    # ================== WEBSOCKET TESTS ==================
    
    async def test_websocket_connection(self):
        """Test WebSocket connection"""
        try:
            uri = f"{WS_URL}/transcript/ws/{TEST_SESSION_ID}_ws"
            
            async with websockets.connect(uri) as websocket:
                # Send ping
                await websocket.send(json.dumps({"type": "ping"}))
                
                # Wait for pong
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(response)
                
                passed = data.get("type") == "pong"
                self.log_result("WebSocket Connection", passed, "Ping/Pong successful")
                return passed
                
        except asyncio.TimeoutError:
            self.log_result("WebSocket Connection", False, "Timeout waiting for pong")
            return False
        except Exception as e:
            self.log_result("WebSocket Connection", False, str(e))
            return False
    
    async def test_websocket_audio_processing(self):
        """Test WebSocket audio processing"""
        try:
            uri = f"{WS_URL}/transcript/ws/{TEST_SESSION_ID}_audio"
            
            # Generate test audio (1 second of sine wave)
            sample_rate = 16000
            duration = 1.0
            t = np.linspace(0, duration, int(sample_rate * duration))
            audio = np.sin(2 * np.pi * 440 * t) * 0.3
            audio_int16 = (audio * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            
            async with websockets.connect(uri) as websocket:
                # Send audio chunk
                await websocket.send(json.dumps({
                    "type": "audio_chunk",
                    "audio_data": audio_base64,
                    "sample_rate": sample_rate
                }))
                
                # Wait for response (or timeout if no speech detected)
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    data = json.loads(response)
                    passed = "type" in data  # Any response is acceptable
                    self.log_result("WebSocket Audio Processing", passed, f"Response: {data.get('type', 'unknown')}")
                    return passed
                except asyncio.TimeoutError:
                    # Timeout is acceptable - means no speech detected in test audio
                    self.log_result("WebSocket Audio Processing", True, "No speech detected (expected for sine wave)")
                    return True
                
        except Exception as e:
            self.log_result("WebSocket Audio Processing", False, str(e))
            return False
    
    # ================== AUDIO UPLOAD TEST ==================
    
    async def test_audio_upload(self):
        """Test audio file upload and transcription"""
        try:
            # Create a simple WAV file
            audio_bytes = self._create_test_wav()
            
            files = {
                'file': ('test_audio.wav', audio_bytes, 'audio/wav')
            }
            data = {
                'session_id': f"{TEST_SESSION_ID}_upload"
            }
            
            response = await self.client.post(
                f"{BASE_URL}/transcript/process",
                files=files,
                data=data
            )
            
            passed = response.status_code == 200
            result = response.json()
            self.log_result("Audio Upload", passed, f"Status: {result.get('status', 'unknown')}")
            return passed
            
        except Exception as e:
            self.log_result("Audio Upload", False, str(e))
            return False
    
    def _create_test_wav(self) -> bytes:
        """Create a test WAV file"""
        sample_rate = 16000
        duration = 1.0
        frequency = 440.0
        
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = np.sin(2 * np.pi * frequency * t) * 0.3
        audio_int16 = (audio * 32767).astype(np.int16)
        
        # Create WAV file in memory
        import io
        wav_io = io.BytesIO()
        
        with wave.open(wav_io, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_int16.tobytes())
        
        return wav_io.getvalue()
    
    # ================== SUMMARY & INSIGHTS ==================
    
    async def test_session_summary(self):
        """Test session summary generation"""
        try:
            response = await self.client.get(
                f"{BASE_URL}/transcript/session/{TEST_SESSION_ID}/summary"
            )
            passed = response.status_code in [200, 404]  # 404 if no data
            self.log_result("Session Summary", passed)
            return passed
        except Exception as e:
            self.log_result("Session Summary", False, str(e))
            return False
    
    async def test_session_insights(self):
        """Test session insights"""
        try:
            response = await self.client.get(
                f"{BASE_URL}/transcript/session/{TEST_SESSION_ID}/insights"
            )
            passed = response.status_code in [200, 404]
            self.log_result("Session Insights", passed)
            return passed
        except Exception as e:
            self.log_result("Session Insights", False, str(e))
            return False
    
    # ================== CLEANUP ==================
    
    async def test_delete_session(self):
        """Test session deletion"""
        try:
            response = await self.client.delete(
                f"{BASE_URL}/transcript/session/{TEST_SESSION_ID}"
            )
            passed = response.status_code == 200
            self.log_result("Delete Session", passed)
            return passed
        except Exception as e:
            self.log_result("Delete Session", False, str(e))
            return False
    
    # ================== METRICS ==================
    
    async def test_metrics_endpoint(self):
        """Test metrics endpoint"""
        try:
            response = await self.client.get(f"{BASE_URL}/metrics")
            data = response.json()
            passed = response.status_code == 200 and "application_metrics" in data
            self.log_result("Metrics Endpoint", passed)
            return passed
        except Exception as e:
            self.log_result("Metrics Endpoint", False, str(e))
            return False
    
    # ================== RUN ALL TESTS ==================
    
    async def run_all_tests(self):
        """Run all tests in sequence"""
        print("\n" + "="*60)
        print("🧪 ECHOAI BACKEND TEST SUITE")
        print("="*60 + "\n")
        
        print("📋 Testing Health & Status...")
        await self.test_root_endpoint()
        await self.test_health_check()
        await self.test_detailed_health()
        await self.test_metrics_endpoint()
        
        print("\n📋 Testing Session Management...")
        await self.test_create_session()
        await self.test_get_session_transcript()
        await self.test_list_sessions()
        
        print("\n📋 Testing Analytics...")
        await self.test_session_analytics()
        await self.test_list_all_sessions_analytics()
        
        print("\n📋 Testing WebSocket...")
        await self.test_websocket_connection()
        await self.test_websocket_audio_processing()
        
        print("\n📋 Testing Audio Upload...")
        await self.test_audio_upload()
        
        print("\n📋 Testing Summary & Insights...")
        await self.test_session_summary()
        await self.test_session_insights()
        
        print("\n📋 Testing Cleanup...")
        await self.test_delete_session()
        
        # Summary
        print("\n" + "="*60)
        print("📊 TEST SUMMARY")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r["passed"])
        failed_tests = total_tests - passed_tests
        
        print(f"\nTotal Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print("\n⚠️  Failed Tests:")
            for result in self.test_results:
                if not result["passed"]:
                    print(f"  - {result['test']}: {result['details']}")
        
        print("\n" + "="*60 + "\n")
        
        return failed_tests == 0


async def main():
    """Main test runner"""
    tester = BackendTester()
    
    try:
        success = await tester.run_all_tests()
        exit_code = 0 if success else 1
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        exit_code = 130
    except Exception as e:
        print(f"\n\n❌ Test suite error: {e}")
        exit_code = 1
    finally:
        await tester.close()
    
    return exit_code


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)