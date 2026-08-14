/**
 * `<script type="application/ld+json">` blokiga JSON joylashtirish uchun
 * xavfsiz seriyalash.
 *
 * `JSON.stringify` `<` belgisini escape QILMAYDI. Agar seriyalanayotgan matnda
 * `</script>` uchrasa, HTML tahlilchisi skript blokini o'sha yerda yopadi va
 * qolgan qism sahifa razmetkasiga aylanadi — saqlangan XSS. Hozir matn repodagi
 * TS fayllardan keladi, lekin landing CMS ulangach u foydalanuvchi kiritmasiga
 * aylanadi, ya'ni teshik o'sha kuni ochiladi.
 *
 * `<` JSON satrida haqiqiy `<` ga teng — razmetka MAZMUNI o'zgarmaydi,
 * qidiruv tizimi bir xil ma'lumotni o'qiydi, faqat HTML tahlilchisi uni
 * yopuvchi teg deb ko'rmaydi.
 *
 * U+2028/U+2029 bu yerda escape qilinmaydi: ld+json bloki BAJARILMAYDI, u
 * ma'lumot sifatida tahlil qilinadi, shuning uchun JS qator ajratgichlari
 * muammo emas.
 */
const ESCAPES: Record<string, string> = {
  '<': '\\u003c',
  '>': '\\u003e',
  '&': '\\u0026',
};

export function jsonLdScript(value: unknown): string {
  return JSON.stringify(value).replace(/[<>&]/g, (char) => ESCAPES[char] ?? char);
}
