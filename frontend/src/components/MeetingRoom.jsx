import React, { useEffect, useState } from 'react';
import useWebSocket from 'react-use-websocket';

const MeetingRoom = () => {
    const { transcripts, participants, activeSpeakerId, chatMessages } = useWebSocket(); // Adjust this section

    // Remaining component code...

    const handleExportTranscript = () => {
        // Implementation of the handleExportTranscript function
    };

    // Other code...

    return (
        <div>
            {/* Component JSX */}
        </div>
    );
};

// Existing code here

export default MeetingRoom;