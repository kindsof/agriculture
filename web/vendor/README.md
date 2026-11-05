# 第三方前端资源

本目录只包含地图所需的第三方库，均已随仓库提供，页面运行时不访问 CDN。

| 目录 | 项目 | 版本 | 许可 |
| --- | --- | --- | --- |
| `leaflet/` | [Leaflet](https://leafletjs.com/) | 1.9.4 | BSD-2-Clause（见 `leaflet/LICENSE`） |
| `leaflet-markercluster/` | [Leaflet.markercluster](https://github.com/Leaflet/Leaflet.markercluster) | 1.5.3 | MIT（见 npm 包元数据；版权归 Leaflet.markercluster contributors） |

Leaflet 的图片资源来自其 npm 发行包 `dist/images/`。MarkerCluster 的 CSS/JS 来自 `dist/`。

省级边界数据不在此目录，见 `../data/provinces.geojson` 与 `../data/SOURCES.md`。
