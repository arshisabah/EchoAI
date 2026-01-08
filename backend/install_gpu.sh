#!/bin/bash
# Install PyTorch with CUDA 12.1 for NVIDIA RTX 3050

echo "==============================================="
echo "Installing PyTorch with CUDA 12.1 Support"
echo "For NVIDIA RTX 3050 GPU Acceleration"
echo "==============================================="

# Activate virtual environment if it exists
if [ -f venv/Scripts/activate ]; then
    source venv/Scripts/activate
    echo "Virtual environment activated"
elif [ -f venv/bin/activate ]; then
    source venv/bin/activate
    echo "Virtual environment activated"
else
    echo "Warning: No venv found, installing globally"
fi

echo ""
echo "Step 1: Installing PyTorch with CUDA 12.1..."
pip uninstall -y torch torchvision torchaudio
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

echo ""
echo "Step 2: Installing other requirements..."
pip install -r requirements.txt

echo ""
echo "==============================================="
echo "Installation Complete!"
echo "Testing GPU availability..."
echo "==============================================="
python -c "import torch; print(f'CUDA Available: {torch.cuda.is_available()}'); print(f'CUDA Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"None\"}')"

echo ""
echo "==============================================="
echo "Setup complete! Your RTX 3050 is ready."
echo "Run 'python -m uvicorn app.main:app --reload' to start"
echo "==============================================="
