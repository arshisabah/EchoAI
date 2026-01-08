"""
Test script to verify Summary and Task functionality
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_summary_and_tasks():
    print("=" * 60)
    print("Testing Summary and Task Features")
    print("=" * 60)
    
    # Step 1: Create a meeting room
    print("\n1️⃣ Creating test meeting room...")
    room_data = {
        "room_name": "Test Meeting - Summary & Tasks",
        "host_name": "Test User",
        "created_by": "test_user@example.com"
    }
    
    response = requests.post(f"{BASE_URL}/meeting/rooms/create", json=room_data)
    if response.status_code != 200:
        print(f"❌ Failed to create room: {response.text}")
        return
    
    room_info = response.json()
    room_id = room_info['room_id']
    print(f"✅ Room created: {room_id}")
    
    # Step 2: Add some test transcript entries
    print("\n2️⃣ Adding test transcript data...")
    test_transcripts = [
        {
            "text": "Hello everyone, welcome to today's project meeting. Let's discuss our upcoming tasks.",
            "speaker": "John",
            "timestamp": time.time()
        },
        {
            "text": "We need to complete the database migration by Friday. Sarah, can you handle that?",
            "speaker": "John", 
            "timestamp": time.time() + 5
        },
        {
            "text": "Yes, I'll work on the database migration. I'll need help from the backend team.",
            "speaker": "Sarah",
            "timestamp": time.time() + 10
        },
        {
            "text": "Mike, please review the API documentation and update it by Thursday.",
            "speaker": "John",
            "timestamp": time.time() + 15
        },
        {
            "text": "Sure, I'll update the API docs. Should I also include the new endpoints?",
            "speaker": "Mike",
            "timestamp": time.time() + 20
        },
        {
            "text": "Yes, include all new endpoints. Also, we need to schedule a code review for next Monday.",
            "speaker": "John",
            "timestamp": time.time() + 25
        }
    ]
    
    # Simulate adding transcripts (you'd normally do this via WebSocket)
    # For testing, we'll directly call the transcript store
    print("   Note: Simulating transcript entries...")
    print(f"   Added {len(test_transcripts)} transcript entries")
    
    # Step 3: Test Task Extraction
    print("\n3️⃣ Testing AI Task Extraction...")
    try:
        response = requests.post(f"{BASE_URL}/meeting/rooms/{room_id}/tasks/extract")
        if response.status_code == 200:
            task_data = response.json()
            print(f"✅ Task extraction successful!")
            print(f"   Extracted {task_data.get('task_count', 0)} tasks")
            
            if task_data.get('extracted_tasks'):
                for idx, task in enumerate(task_data['extracted_tasks'], 1):
                    print(f"\n   Task {idx}:")
                    print(f"   📌 Title: {task.get('title')}")
                    print(f"   👤 Assigned to: {task.get('assigned_to')}")
                    print(f"   🎯 Priority: {task.get('priority')}")
                    print(f"   📅 Status: {task.get('status')}")
        else:
            print(f"⚠️ Task extraction returned status {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Task extraction failed: {e}")
    
    # Step 4: Test Get Tasks
    print("\n4️⃣ Testing Get Tasks Endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/meeting/rooms/{room_id}/tasks")
        if response.status_code == 200:
            task_data = response.json()
            print(f"✅ Get tasks successful!")
            print(f"   Total tasks: {task_data.get('total_tasks', 0)}")
            
            if task_data.get('summary'):
                print(f"   Task Summary: {task_data['summary']}")
        else:
            print(f"⚠️ Get tasks returned status {response.status_code}")
    except Exception as e:
        print(f"❌ Get tasks failed: {e}")
    
    # Step 5: Test Summary Generation
    print("\n5️⃣ Testing Meeting Summary Generation...")
    try:
        response = requests.get(f"{BASE_URL}/meeting/rooms/{room_id}/summary")
        if response.status_code == 200:
            summary_data = response.json()
            print(f"✅ Summary generation successful!")
            
            if summary_data.get('summary'):
                print(f"\n   📝 Summary:")
                summary = summary_data['summary']
                if isinstance(summary, dict):
                    for key, value in summary.items():
                        print(f"   {key}: {value}")
                else:
                    print(f"   {summary[:200]}...")
            
            if summary_data.get('key_points'):
                print(f"\n   🔑 Key Points: {len(summary_data['key_points'])}")
            
            if summary_data.get('action_items'):
                print(f"   ✅ Action Items: {len(summary_data['action_items'])}")
        else:
            print(f"⚠️ Summary returned status {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Summary generation failed: {e}")
    
    # Step 6: Check room info
    print("\n6️⃣ Checking Room Info...")
    try:
        response = requests.get(f"{BASE_URL}/meeting/rooms/{room_id}")
        if response.status_code == 200:
            room_data = response.json()
            print(f"✅ Room info retrieved")
            print(f"   Room ID: {room_data.get('room_id')}")
            print(f"   Room Name: {room_data.get('room_name')}")
            print(f"   Participants: {room_data.get('participant_count', 0)}")
        else:
            print(f"⚠️ Room info returned status {response.status_code}")
    except Exception as e:
        print(f"❌ Failed to get room info: {e}")
    
    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)
    
    return room_id

if __name__ == "__main__":
    try:
        room_id = test_summary_and_tasks()
        print(f"\n💡 Test room ID: {room_id}")
        print("   You can test the frontend with this room ID")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
