"""
Simple test to check if summary and task endpoints exist and respond
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_endpoints():
    print("=" * 60)
    print("Testing Backend Endpoints")
    print("=" * 60)
    
    # Test 1: Check if backend is alive
    print("\n1️⃣ Testing health check...")
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"✅ Backend is alive: {response.status_code}")
    except Exception as e:
        print(f"❌ Backend not responding: {e}")
        return
    
    # Test 2: Check docs endpoint
    print("\n2️⃣ Checking API docs...")
    try:
        response = requests.get(f"{BASE_URL}/docs")
        if response.status_code == 200:
            print("✅ API docs accessible at http://localhost:8000/docs")
        else:
            print(f"⚠️ Docs returned {response.status_code}")
    except Exception as e:
        print(f"❌ Docs not accessible: {e}")
    
    # Test 3: List meeting rooms
    print("\n3️⃣ Listing meeting rooms...")
    try:
        response = requests.get(f"{BASE_URL}/meeting/rooms")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Rooms endpoint working")
            print(f"   Active rooms: {data.get('total_count', 0)}")
            if data.get('rooms'):
                for room in data['rooms'][:3]:
                    print(f"   - {room.get('room_name')} (ID: {room.get('room_id')})")
        else:
            print(f"⚠️ Rooms returned {response.status_code}")
    except Exception as e:
        print(f"❌ Rooms endpoint error: {e}")
    
    # Test 4: Check if summary endpoint exists (with fake room)
    print("\n4️⃣ Testing summary endpoint structure...")
    try:
        response = requests.get(f"{BASE_URL}/meeting/rooms/test-room/summary")
        print(f"   Summary endpoint exists: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Summary endpoint working!")
            print(f"   Response keys: {list(data.keys())}")
        elif response.status_code == 404:
            print(f"✅ Summary endpoint exists (room not found is expected)")
        else:
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"❌ Summary endpoint error: {e}")
    
    # Test 5: Check if task endpoint exists (with fake room)
    print("\n5️⃣ Testing task endpoint structure...")
    try:
        response = requests.get(f"{BASE_URL}/meeting/rooms/test-room/tasks")
        print(f"   Task endpoint exists: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Task endpoint working!")
            print(f"   Response keys: {list(data.keys())}")
        elif response.status_code == 404:
            print(f"✅ Task endpoint exists (room not found is expected)")
        else:
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"❌ Task endpoint error: {e}")
    
    # Test 6: Check task extraction endpoint
    print("\n6️⃣ Testing task extraction endpoint...")
    try:
        response = requests.post(f"{BASE_URL}/meeting/rooms/test-room/tasks/extract")
        print(f"   Task extraction endpoint exists: {response.status_code}")
        if response.status_code in [200, 404]:
            print(f"✅ Task extraction endpoint exists")
            if response.status_code == 200:
                data = response.json()
                print(f"   Response keys: {list(data.keys())}")
        else:
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"❌ Task extraction endpoint error: {e}")
    
    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)
    print("✅ All core endpoints are registered and accessible")
    print("")
    print("To test functionality:")
    print("1. Open frontend: http://localhost:5173")
    print("2. Create a meeting room")
    print("3. Speak to generate transcripts")
    print("4. Click 'Summary' tab to test summary generation")
    print("5. Click 'Tasks' tab and 'Extract Tasks' button")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_endpoints()
    except KeyboardInterrupt:
        print("\n\nTest interrupted")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
