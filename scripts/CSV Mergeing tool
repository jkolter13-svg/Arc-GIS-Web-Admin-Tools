"""
CSV and Excel File Merger Tool
===============================
This module provides a GUI-based tool to merge multiple CSV and Excel files 
from a specified folder into a single output file. It uses pandas for data 
manipulation and tkinter for the user interface.

Key Features:
- Supports CSV (.csv), Excel 2007+ (.xlsx), and Excel 97-2003 (.xls) formats
- Automatically adds a "Source_File" column to track which file each row came from
- Allows user to choose input folder and output file path via dialog boxes
- Handles file I/O errors gracefully with user-friendly error messages
- Cross-platform path handling with proper normalization
"""

# ============================================================================
# IMPORTS
# ============================================================================

# tkinter: Python's standard GUI library for creating dialog windows
import tkinter as tk
from tkinter import simpledialog, messagebox

# pathlib: Modern path handling for cross-platform compatibility
from pathlib import Path

# pandas: Data manipulation library for reading/writing data files
# (wrapped in try/except to provide helpful error message if not installed)
try:
    import pandas as pd
except ImportError:
    pd = None


# ============================================================================
# CONSTANTS
# ============================================================================

# Set of supported file extensions that the tool can process
# CSV: Comma-separated values (plain text format)
# XLSX: Excel 2007+ format (modern Excel spreadsheets)
# XLS: Excel 97-2003 format (legacy Excel spreadsheets)
SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def prompt_for_path(prompt_text, initial_value=""):
    """
    Display a dialog box to prompt the user for a file path.
    
    This function creates a hidden root tkinter window and displays a 
    string input dialog. The window is set to always appear on top.
    
    Parameters:
    -----------
    prompt_text : str
        The label/question text displayed to the user in the dialog
    initial_value : str, optional
        Pre-filled text in the input field (default: empty string)
    
    Returns:
    --------
    str or None
        The path string entered by the user, or None if they cancelled
    
    Note:
    -----
    The dialog is set with "-topmost" attribute to ensure it appears above 
    other windows on the desktop.
    """
    # Create and hide the root tkinter window
    root = tk.Tk()
    root.withdraw()  # Hide the window - we only want the dialog box visible
    
    # Set the dialog to appear on top of all other windows
    root.attributes("-topmost", True)
    
    # Display the string input dialog and capture user input
    value = simpledialog.askstring("Path", prompt_text, initialvalue=initial_value)
    
    # Clean up: destroy the root window after dialog is closed
    root.destroy()
    
    return value


def normalize_path(raw_path):
    """
    Normalize and clean a file path string.
    
    This function handles user input paths which may contain extra quotes,
    whitespace, or use the ~ home directory shortcut. It converts them to
    standardized, cross-platform compatible paths.
    
    Parameters:
    -----------
    raw_path : str
        The raw path string as entered by the user (may contain quotes, spaces, ~)
    
    Returns:
    --------
    str
        Normalized path as a string, or empty string if input was empty/None
    
    Examples:
    ---------
    >>> normalize_path('  "C:\\Users\\user\\folder"  ')
    'C:\\Users\\user\\folder'
    
    >>> normalize_path('~/Documents/file.csv')
    '/home/user/Documents/file.csv'  # (expands ~ to user's home directory)
    """
    # Return empty string if raw_path is None or falsy
    if not raw_path:
        return ""
    
    # Strip leading/trailing whitespace and remove surrounding quotes if present
    # Then expand ~ to the user's home directory
    # Finally convert to string (pathlib.Path object -> str)
    return str(Path(raw_path.strip().strip('"')).expanduser())


def ensure_output_path(output_path):
    """
    Validate and prepare the output path for file writing.
    
    This function ensures that:
    1. The output path has a valid file extension (defaults to .xlsx if missing)
    2. All necessary parent directories exist (creates them if needed)
    3. The user has write permissions to the target directory
    
    Parameters:
    -----------
    output_path : str
        The desired output file path (may or may not have an extension)
    
    Returns:
    --------
    pathlib.Path
        A Path object pointing to the validated output file location
    
    Raises:
    -------
    PermissionError
        If the output directory is not writable
    
    Note:
    -----
    Performs a write permission test by creating and immediately deleting
    a temporary file in the output directory.
    """
    # Convert to Path object and expand home directory if needed
    output = Path(output_path).expanduser()
    
    # If file has no supported extension, default to .xlsx format
    if output.suffix.lower() not in {".csv", ".xlsx", ".xls"}:
        output = output.with_suffix(".xlsx")

    try:
        # Create all parent directories (parents=True) if they don't exist
        # exist_ok=True prevents errors if directories already exist
        output.parent.mkdir(parents=True, exist_ok=True)
        
        # Test write permissions by creating a temporary test file
        # This ensures we fail early if user lacks permissions rather than
        # discovering the problem when trying to write the actual output file
        test_file = output.parent / ".merge_tool_write_test.tmp"
        test_file.touch(exist_ok=True)  # Create the test file
        test_file.unlink(missing_ok=True)  # Immediately delete the test file
        
    except PermissionError as exc:
        # User lacks write permissions - raise descriptive error message
        raise PermissionError(
            f"Cannot write to '{output.parent}'. Choose a folder you can write to."
        ) from exc

    return output


def find_data_files(folder):
    """
    Discover all CSV and Excel files in a specified folder.
    
    Scans the given folder and returns a list of all supported data files
    (CSV, XLSX, and XLS formats). Results are sorted alphabetically by 
    filename for consistent ordering.
    
    Parameters:
    -----------
    folder : str
        Path to the folder to scan
    
    Returns:
    --------
    list of pathlib.Path
        Sorted list of Path objects for each data file found
    
    Raises:
    -------
    FileNotFoundError
        If the specified folder does not exist
    NotADirectoryError
        If the path exists but is not a directory (e.g., it's a file)
    FileNotFoundError
        If no supported data files are found in the folder
    """
    # Convert to Path object and expand home directory if needed
    folder_path = Path(folder).expanduser()
    
    # Validate that the folder exists
    if not folder_path.exists():
        raise FileNotFoundError(f"Folder not found: {folder_path}")
    
    # Validate that the path is actually a directory, not a file
    if not folder_path.is_dir():
        raise NotADirectoryError(f"This is not a folder: {folder_path}")

    # Iterate through all items in the folder and collect data files
    files = []
    for item in folder_path.iterdir():
        # Check if item is a file (not a directory) and has a supported extension
        if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(item)
    
    # Sort files alphabetically by filename (case-insensitive) for consistent results
    # This ensures the merge order is predictable regardless of filesystem order
    return sorted(files, key=lambda p: p.name.lower())


def read_file_to_dataframe(file_path):
    """
    Read a CSV or Excel file into a pandas DataFrame.
    
    Automatically detects file type based on extension and uses the 
    appropriate pandas reader function. Returns all data as strings
    to prevent unexpected type conversions.
    
    Parameters:
    -----------
    file_path : pathlib.Path
        Path object pointing to the file to read
    
    Returns:
    --------
    pandas.DataFrame
        DataFrame containing the file data with all columns as strings
    
    Raises:
    -------
    ValueError
        If the file extension is not supported (not .csv, .xlsx, or .xls)
    
    Notes:
    ------
    - dtype=str: All columns are read as strings, preventing pandas from
                 auto-converting values to numeric/datetime types
    - keep_default_na=False: Prevents pandas from treating certain string 
                             values (like "NA") as missing values
    """
    # Get the file extension and convert to lowercase for comparison
    ext = file_path.suffix.lower()
    
    # Handle CSV files
    if ext == ".csv":
        # dtype=str: treat all columns as strings (no auto type conversion)
        # keep_default_na=False: don't convert "NA" or similar to NaN
        return pd.read_csv(file_path, dtype=str, keep_default_na=False)
    
    # Handle Excel files (both modern .xlsx and legacy .xls formats)
    if ext in {".xlsx", ".xls"}:
        return pd.read_excel(file_path, dtype=str, keep_default_na=False)
    
    # If we get here, the file type is not supported (shouldn't happen due to earlier validation)
    raise ValueError(f"Unsupported file type: {file_path}")


def merge_files(input_folder, output_path):
    """
    Merge multiple CSV/Excel files from a folder into a single output file.
    
    This is the core function that orchestrates the entire merge process:
    1. Validates that pandas is installed
    2. Normalizes input/output paths
    3. Discovers all data files in the input folder
    4. Reads each file into a DataFrame
    5. Adds a "Source_File" column to track which file each row came from
    6. Concatenates all DataFrames vertically (row-wise)
    7. Writes the combined data to the output file
    
    Parameters:
    -----------
    input_folder : str
        Path to the folder containing data files to merge
    output_path : str
        Path where the merged output file should be saved
    
    Returns:
    --------
    pathlib.Path
        Path object pointing to the created merged output file
    
    Raises:
    -------
    ImportError
        If pandas is not installed in the Python environment
    FileNotFoundError
        If input folder doesn't exist or contains no data files
    PermissionError
        If output file cannot be written
    """
    # Check that pandas is available (it should be, but provide helpful error if not)
    if pd is None:
        raise ImportError("pandas is required. Install it in your Python environment first.")

    # Normalize the input and output paths (handle quotes, spaces, ~, etc.)
    input_folder = normalize_path(input_folder)
    output_path = normalize_path(output_path)

    # Discover all CSV/Excel files in the input folder, sorted alphabetically
    files = find_data_files(input_folder)
    if not files:
        raise FileNotFoundError("No CSV or Excel files were found in the selected folder.")

    # Initialize the combined DataFrame as None (will hold merged data)
    combined_df = None
    
    # Process each data file
    for file_path in files:
        # Read the file into a pandas DataFrame
        df = read_file_to_dataframe(file_path)
        
        # Skip empty files (no data rows)
        if df.empty:
            continue

        # Make a copy to avoid modifying the original DataFrame object
        # (good practice when modifying data)
        df = df.copy()
        
        # Add a new column that tracks which source file this row came from
        # This is essential for tracing data back to its origin after merging
        df["Source_File"] = file_path.name

        # Initialize combined_df with the first non-empty file's data
        if combined_df is None:
            combined_df = df
        else:
            # Concatenate subsequent files to the combined DataFrame
            # ignore_index=True: reset row indices to maintain 0, 1, 2... sequence
            # sort=False: preserve column order from first file (don't reorder columns)
            combined_df = pd.concat([combined_df, df], ignore_index=True, sort=False)

    # Prepare the output path (validate, create directories, check permissions)
    output = ensure_output_path(output_path)

    try:
        # Write the merged DataFrame to the output file in the appropriate format
        if output.suffix.lower() == ".csv":
            # For CSV format: write to CSV without row index column
            combined_df.to_csv(output, index=False)
        else:
            # For Excel format (.xlsx or .xls): write to Excel without row index column
            combined_df.to_excel(output, index=False)
    except PermissionError as exc:
        # If write fails due to permissions, provide descriptive error
        raise PermissionError(
            f"Permission denied while saving '{output}'. Choose a different output path."
        ) from exc

    return output


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """
    Main application entry point - orchestrates the user interaction workflow.
    
    Workflow:
    1. Prompt user to select input folder via dialog box
    2. Prompt user to specify output file path (with suggested default)
    3. Call merge_files() to perform the actual merge operation
    4. Show success or error message to the user via dialog box
    
    This function handles all user interaction through dialog boxes and
    error reporting.
    """
    # STEP 1: Prompt user for input folder path
    folder = normalize_path(prompt_for_path("Enter the folder path containing the CSV/Excel files"))
    
    # If user cancelled the folder selection dialog, exit gracefully
    if not folder:
        messagebox.showinfo("Cancelled", "No folder path entered.")
        return

    # STEP 2: Prompt user for output file path
    # Provide a sensible default: merged.xlsx in the same input folder
    output_path = normalize_path(
        prompt_for_path(
            "Enter the output file path (for example: C:/temp/merged.xlsx or C:/temp/merged.csv)",
            initial_value=str(Path(folder) / "merged.xlsx"),  # Default suggestion
        )
    )
    
    # If user cancelled the output path selection dialog, exit gracefully
    if not output_path:
        messagebox.showinfo("Cancelled", "No output path entered.")
        return

    # STEP 3: Attempt to merge files
    try:
        # Call the merge function with user's input paths
        result = merge_files(folder, output_path)
        
        # Merge succeeded - show success message with output file path
        messagebox.showinfo(
            "Done",
            f"Merged files successfully into:\n{result}",
        )
    except Exception as exc:
        # Merge failed - show error message with details
        # (Exception type and message are automatically caught and displayed)
        messagebox.showerror("Merge failed", str(exc))


# ============================================================================
# SCRIPT EXECUTION
# ============================================================================

# Check if this script is being run directly (not imported as a module)
# If so, execute the main() function to start the application
if __name__ == "__main__":
    main()
