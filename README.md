# Lost City of Z

## Overview

Lost City of Z is an open-source project for gathering and analyzing satellite imagery and elevation data for the Chapada Diamantina region in Brazil. The project automates the collection of:

- Sentinel-2 L2A satellite imagery (true-color bands)
- SRTM-1 arc-second elevation data
- Planet NICFI monthly mosaics

## Features

- Automated download of Sentinel-2 L2A scenes with configurable cloud cover thresholds
- SRTM-1 arc-second DEM tile collection
- Planet NICFI mosaic integration (requires API key)
- Configurable bounding box and date ranges
- Efficient file management and download handling

## Getting Started

### Prerequisites

- Python 3.x
- Required Python packages:
  ```bash
  pip install pystac-client planetary-computer shapely rasterio requests boto3
  ```
- Environment variables:
  - `AWS_NO_SIGN_REQUEST=YES` (for SRTM data access)
  - `PL_API_KEY` (optional, for Planet NICFI data)

### Installation

1. Clone this repository
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up the required environment variables

## Usage

The script is configured to gather data for the following bounding box (WGS-84):

- West: -41.65
- South: -12.80
- East: -40.95
- North: -12.10

By default, it collects:

- Sentinel-2 L2A scenes with <20% cloud cover since January 2024
- All SRTM-1 arc-second tiles overlapping the box
- NICFI March 2024 mosaic quads intersecting the box

Run the script:

```bash
python main.py
```

## Contributing

This project is open source and welcomes contributions! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

**Alex Hughes**

- GitHub: [@alexjackhughes](https://github.com/alexjackhughes)
- Website: [alexjackhughes.com](https://alexjackhughes.com)

## Acknowledgments

- Microsoft Planetary Computer for Sentinel-2 data access
- Planet Labs for NICFI mosaics
- NASA for SRTM elevation data
