# Zidoo UHD cho Home Assistant

Custom integration (HACS) điều khiển đầu phát **Zidoo** (UHD8000, UHD5000, Z3000 Pro, Z2000 Pro, Z9X…) qua **API HTTP của Zidoo (cổng 9529)**. Không cần thư viện ngoài.

## Entity

| Entity | Chức năng |
|---|---|
| `media_player` | Bật (Wake-on-LAN), tắt (`Key.PowerOn.Poweroff`), play/pause/stop, next/previous, seek, tăng/giảm/mute âm lượng, chọn app (source), phát file/URL (`play_media`). Hiển thị tên phim/bài hát, thời lượng, vị trí; thuộc tính độ phân giải, fps, định dạng âm thanh |
| `remote` | Gửi mọi phím remote: `home`, `ok`, `up`, `down`, `left`, `right`, `back`, `menu`, `info`, `subtitle`, `audio`, `0`–`9`, `red`/`green`/`yellow`/`blue`… hoặc mã gốc `Key.xxx` |
| `select` Track âm thanh | Chọn track audio của phim đang phát |
| `select` Phụ đề | Chọn phụ đề của phim đang phát |
| `select` Ngõ ra âm thanh | HDMI / HDMI Audio / XLR / RCA / SPDIF… (tùy model) |
| `button` Chuyển TV sang Zidoo | Gửi phím Home, nhờ HDMI-CEC TV tự chuyển sang cổng HDMI của Zidoo |
| `button` Chapter kế tiếp / trước | Nhảy chapter phim |
| `button` Restart | Khởi động lại đầu Zidoo |

## Cài đặt

1. HACS → Custom repositories → `https://github.com/lamntevohome-gif/ha-zidoo` (loại *Integration*).
2. Cài **Zidoo UHD**, khởi động lại Home Assistant.
3. Settings → Devices & services → Add integration → **Zidoo UHD** → nhập IP (đầu Zidoo phải đang bật).

**Mật khẩu điều khiển** chỉ cần nhập khi bạn có đặt mật khẩu cho điều khiển qua mạng trên Zidoo.

## Bật / tắt

| Lệnh | Integration gửi | Ghi chú |
|---|---|---|
| **turn_on** | **Wake-on-LAN** (theo MAC, gửi tới `255.255.255.255` và `x.x.x.255` của mạng) | Zidoo đang bật thì bỏ qua gói tin, nên không bao giờ làm máy tắt |
| **turn_off** | **`Key.PowerOn.Poweroff`** | Lệnh tắt một chiều. Zidoo đã tắt thì không có IP, lệnh không tới, nên không bao giờ làm máy bật |

- Zidoo cần cắm **dây LAN** để Wake-on-LAN hoạt động; UHD8000 báo `ableRemoteBoot: true`.
- Nên đặt **DHCP reservation** (IP cố định) cho Zidoo trên router.
- Home Assistant chạy Docker cần `network_mode: host` để gói Wake-on-LAN ra được mạng LAN.
- Sau khi turn on, integration theo dõi quá trình khởi động tối đa 90 giây để chuyển sang *on* sớm. Sau khi turn off, entity chuyển *off* ngay.
- Phím nguồn gốc (`power`, bật/tắt luân phiên) vẫn gửi được qua `remote.send_command` khi cần.

## Chuyển TV sang Zidoo (HDMI-CEC)

1. Trên TV: bật Anynet+ / HDMI-CEC.
2. Trên Zidoo: Settings → Other settings → bật **HDMI CEC**. Dây HDMI vào TV phải cắm ở **cổng HDMI chính** của Zidoo, vì CEC chỉ chạy trên cổng này.
3. Bấm nút **Chuyển TV sang Zidoo**, hoặc dùng trong automation:

```yaml
action: button.press
target:
  entity_id: button.zidoo_uhd8000_chuyen_tv_sang_zidoo   # xem tên thật trong Developer Tools
```

## Ví dụ gửi phím

```yaml
action: remote.send_command
target:
  entity_id: remote.zidoo_uhd8000_remote
data:
  command: [home, down, down, ok]
  delay_secs: 0.4
```

## Phát file

```yaml
action: media_player.play_media
target:
  entity_id: media_player.zidoo_uhd8000
data:
  media_content_type: video
  media_content_id: "smb://192.168.1.10/Movies/Dune.mkv"
```

## Source đang mở

API của Zidoo không báo app đang hiển thị, nên `source` được xác định như sau:

| Tình huống | `source` | `source_origin` |
|---|---|---|
| Đang phát phim bằng trình phát Zidoo | Video player | `player` (chắc chắn) |
| Đang phát nhạc bằng Music player | Music player | `player` (chắc chắn) |
| Mở app hoặc bấm Home từ Home Assistant | Tên app / Home | `home_assistant` |
| Phát xong phim/nhạc, tắt máy, hoặc chưa biết | trống | – |

Nếu bạn mở app bằng remote thật, Home Assistant không biết được. Muốn biết chính xác app đang mở thì phải dùng ADB (integration Android Debug Bridge).

## Ghi chú

- Trạng thái được cập nhật mỗi 2 giây khi đầu đang bật, 10 giây khi đang tắt.
- **Âm lượng:** nếu máy trả về `volumeData` (UHD8000 có trả về), entity có thanh âm lượng (đọc và đặt mức, thang 0–max của máy), trạng thái mute, và các thuộc tính `volume_raw`, `volume_max`, `volume_output`. Khi xuất bitstream sang ampli, nên chỉnh âm lượng ở ampli.
- API được tham khảo từ tài liệu nhà phát triển của Zidoo và integration cộng đồng `wizmo2/zidoo-player`.
