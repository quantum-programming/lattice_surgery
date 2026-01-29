# out2png

## Building and Running the Project

0. **Install Rust**
   If you are a WSL user, run the following command to install Rust:
   (Ref: [Official Rust Installation](https://www.rust-lang.org/ja/tools/install))

   ```bash
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   ```

1. **Move to the Project Directory:**
   Navigate to the `other/out2png` directory in your terminal:

   ```bash
   cd other/out2png
   ```

2. **Set Up the Text File**
   In `targets.txt`, specify the paths to the text files you want to convert.

3. **convert to png**
   With some virtual environment, run the following command:

   ```bash
   python3 main.py
   ```

   We build and run the Rust project in this script.
