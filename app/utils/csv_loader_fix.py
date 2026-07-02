# Fix for _csv_line_iterator function
# The original implementation was incorrect - it wrapped each line in its own reader
# This caused issues when the generator was expected to yield parsed CSV rows

def _csv_line_iterator(iterable):
    """Generator that handles quoted fields in CSV lines.
    
    Each line is treated as a complete CSV row with proper quote handling.
    
    Args:
        iterable: An iterable of lines (strings)
        
    Yields:
        A single list containing the parsed values from one CSV line.
    """
    import csv
    for line in iterable:
        # Parse the entire line as a CSV row
        reader = csv.reader([line])
        yield next(reader)  # This returns a list of values for this line

