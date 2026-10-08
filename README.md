# Zidoo UHD cho Home Assistant

Custom integration (HACS) điều khiển đầu phát **Zidoo** (UHD8000, UHD5000, Z3000 Pro, Z2000 Pro, Z9X…) qua **API HTTP của Zidoo (cổng 9529)**. Không cần thư viện ngoài.

## Entity

| Entity | Chức năng |
|---|---|
| `media_player` | Bật (Wake-on-LAN + PowerOn), tắt (standby hoặc tắt hẳn), play/pause/stop, next/previous, seek, tăng/giảm/mute âm lượng, chọn app (source), phát file/URL (`play_media`). Hiển thị tên phim/bài hát, thời lượng, vị trí; thuộc tính độ phân giải, fps, định dạng âm thanh |
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

## Bật từ standby

- Integration gửi Wake-on-LAN tới địa chỉ MAC lấy được lúc cài đặt, kèm thêm phím PowerOn.
- Trên Zidoo, kiểm tra trong Settings → Other settings → **Power mode**, cho phép đánh thức qua mạng. Nên cắm dây mạng LAN, vì đánh thức qua Wi-Fi kém ổn định hơn.
- Trong **Configure**, chọn khi tắt là *Standby* để bật lại nhanh và vẫn đánh thức được qua mạng.

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

## Ghi chú

- Trạng thái được cập nhật mỗi 2 giây khi đầu đang bật, 10 giây khi đang tắt.
- Âm lượng chỉ có tăng/giảm/mute dạng phím, vì API không trả về mức âm lượng hiện tại.
- API được tham khảo từ tài liệu nhà phát triển của Zidoo và integration cộng đồng `wizmo2/zidoo-player`.
