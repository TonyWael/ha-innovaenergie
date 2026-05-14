# Innova Energie — Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/TonyWael/ha-innovaenergie.svg)](https://github.com/TonyWael/ha-innovaenergie/releases)

A Home Assistant custom integration for [Innova Energie](https://www.innovaenergie.nl) customers. Pulls electricity and gas data from the [mijn.innovaenergie.nl](https://mijn.innovaenergie.nl) portal into Home Assistant, including live usage, meter positions, costs, and current tariff rates.

---

## What it provides

**19 sensors** across electricity and gas:

| Sensor | Unit | Description |
|--------|------|-------------|
| Electricity supply | kWh | Electricity consumed from grid (yesterday) |
| Electricity return | kWh | Electricity returned to grid / solar (yesterday) |
| Electricity net usage | kWh | Net consumption after solar return (yesterday) |
| Electricity last reading | kWh | Most recent hourly consumption reading |
| Electricity this month | kWh | Running total for the current month |
| Electricity meter position | kWh | Cumulative meter reading (high + low tariff combined) |
| Electricity high tariff | EUR/kWh | Current normaaltarief incl. all taxes |
| Electricity low tariff | EUR/kWh | Current daltarief incl. all taxes |
| Electricity cost | EUR | Electricity cost (yesterday) |
| Electricity cost this month | EUR | Electricity cost month-to-date |
| Gas usage | m³ | Gas consumed (yesterday) |
| Gas last reading | m³ | Most recent hourly gas reading |
| Gas this month | m³ | Running total for the current month |
| Gas meter position | m³ | Cumulative meter reading |
| Gas tariff | EUR/m³ | Current gas rate incl. all taxes |
| Gas cost | EUR | Gas cost (yesterday) |
| Gas cost this month | EUR | Gas cost month-to-date |
| Total cost | EUR | Total energy cost (yesterday) |
| Total cost this month | EUR | Total energy cost month-to-date |

All sensors include a `data_date` attribute indicating which date the data is sourced from.

> **Note:** Usage and cost data reflects the most recently completed day (typically yesterday), as Innova Energie's API provides data with a ~1 day lag.

---

## Requirements

- Home Assistant 2023.4 or newer
- An active [Innova Energie](https://www.innovaenergie.nl) account with access to [mijn.innovaenergie.nl](https://mijn.innovaenergie.nl)
- Your Innova Energie **username** (this may be a numeric customer number, not necessarily an email address) and **password**

---

## Installation

### Via HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations**
3. Click the menu (⋮) and choose **Custom repositories**
4. Add `https://github.com/TonyWael/ha-innovaenergie` as an **Integration**
5. Search for **Innova Energie** and install it
6. Restart Home Assistant

Once it is available in the HACS default repository, you can find it directly by searching "Innova Energie" in HACS without adding a custom repository.

### Manual installation

1. Download the latest release from the [releases page](https://github.com/TonyWael/ha-innovaenergie/releases)
2. Copy the `custom_components/innovaenergie` folder into your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Innova Energie**
3. Enter your username and password for mijn.innovaenergie.nl
4. Click **Submit**

The integration will automatically discover your electricity and gas contracts, EAN codes, and tariff rates.

---

## Energy Dashboard

The meter position sensors are compatible with Home Assistant's built-in **Energy Dashboard**:

- **Electricity grid consumption:** use `Electricity meter position`
- **Gas consumption:** use `Gas meter position`
- **Cost tracking:** use `Electricity high tariff` / `Electricity low tariff` / `Gas tariff` as "current price" entities, or enter a static price

To configure:
1. Go to **Settings → Dashboards → Energy** (or click **Energy** in the sidebar)
2. Under **Electricity grid**, click **Add grid connection** and select **Electricity meter position**
3. For cost tracking, select **Use an entity with current price** and choose the appropriate tariff sensor
4. Under **Gas consumption**, add **Gas meter position** and set the gas tariff sensor as the price entity

---

## Data refresh

The integration polls Innova Energie's API every **hour**. Innova Energie updates usage data approximately once per hour, with a ~1 day lag for daily totals.

---

## Troubleshooting

Enable debug logging by adding this to your `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.innovaenergie: debug
```

Then restart Home Assistant and check **Settings → System → Logs** (click **Home Assistant Core**).

Common issues:
- **"Invalid username or password"** — verify your credentials on [mijn.innovaenergie.nl](https://mijn.innovaenergie.nl). Note that your username may be a numeric customer number.
- **Sensors show "Unknown"** — the first poll may not have completed yet; wait up to 1 hour or reload the integration via **Settings → Devices & Services → Innova Energie → Reload**.
- **Tariff sensors show "Unknown"** — the integration needs at least one successful authentication cycle to discover contract UUIDs. Reload the integration.

---

## Contributing

Pull requests and bug reports are welcome. Please open an issue before submitting large changes.

---

## License

MIT License — see [LICENSE](LICENSE) for details.
