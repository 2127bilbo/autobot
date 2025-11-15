"""
Autobot 2.0 - API Stats Helper
Provides API health statistics for UI display
"""

from core.enhanced_api_system import get_enhanced_api


def get_monitor_api_stats(monitor) -> dict:
    """
    Get API usage statistics for a monitor

    Args:
        monitor: Monitor instance

    Returns:
        Dict with API usage stats
    """
    if not hasattr(monitor, 'api_stats'):
        return {
            'api_success': 0,
            'html_fallback': 0,
            'total_checks': 0,
            'api_success_rate': 0.0
        }

    stats = monitor.api_stats.copy()
    total = stats['api_success'] + stats['html_fallback']
    stats['total_checks'] = total

    if total > 0:
        stats['api_success_rate'] = (stats['api_success'] / total) * 100
    else:
        stats['api_success_rate'] = 0.0

    return stats


def get_global_api_health() -> dict:
    """
    Get global API endpoint health stats

    Returns:
        Dict with endpoint health information
    """
    try:
        enhanced_api = get_enhanced_api()
        return enhanced_api.get_stats()
    except:
        return {
            'total_endpoints': 0,
            'healthy_endpoints': 0,
            'unhealthy_endpoints': 0,
            'best_endpoint': None,
            'best_success_rate': 0.0,
            'cached_endpoint': None,
            'cache_valid': False
        }


def format_api_stats_for_display(monitor) -> str:
    """
    Format API stats for console/UI display

    Args:
        monitor: Monitor instance

    Returns:
        Formatted string with API statistics
    """
    stats = get_monitor_api_stats(monitor)

    lines = []
    lines.append("API Statistics:")
    lines.append(f"  API Success: {stats['api_success']}")
    lines.append(f"  HTML Fallback: {stats['html_fallback']}")
    lines.append(f"  Total Checks: {stats['total_checks']}")
    lines.append(f"  API Success Rate: {stats['api_success_rate']:.1f}%")

    return "\n".join(lines)


def format_global_api_health() -> str:
    """
    Format global API health for display

    Returns:
        Formatted string with endpoint health
    """
    health = get_global_api_health()

    lines = []
    lines.append("Global API Health:")
    lines.append(f"  Total Endpoints: {health['total_endpoints']}")
    lines.append(f"  Healthy: {health['healthy_endpoints']}")
    lines.append(f"  Unhealthy: {health['unhealthy_endpoints']}")
    lines.append(f"  Best Success Rate: {health['best_success_rate']:.1%}")

    if health['cache_valid']:
        lines.append(f"  Cached Endpoint: Active")
    else:
        lines.append(f"  Cached Endpoint: None")

    return "\n".join(lines)
