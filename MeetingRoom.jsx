import React, { useEffect } from 'react';
import { useWebSocket } from 'your-websocket-hook';

function MeetingRoom() {
    const { sendMessage, activeSpeakerId } = useWebSocket(); // Added activeSpeakerId here

    useEffect(() => {
        // Your useEffect logic here
    }, []);

    return (
        <div>
            <h1>Meeting Room</h1>
            {/* Other component code */}
        </div>
    );
}

export default MeetingRoom;