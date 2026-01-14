#!/usr/bin/env python3
"""Quick script to inspect the ONNX model's input/output shapes"""
import onnxruntime as ort
import sys

model_path = "assets/models/g1/asap/dec_loco/my_mjlab_loco/g1_velocity.onnx"

print(f"Loading ONNX model from: {model_path}")
session = ort.InferenceSession(model_path)

print("\n=== INPUT INFO ===")
for inp in session.get_inputs():
    print(f"Name: {inp.name}")
    print(f"Shape: {inp.shape}")
    print(f"Type: {inp.type}")
    print()

print("=== OUTPUT INFO ===")
for out in session.get_outputs():
    print(f"Name: {out.name}")
    print(f"Shape: {out.shape}")
    print(f"Type: {out.type}")
    print()
