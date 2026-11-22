// CPU cost of one main-waveform frame per colour style (R&D, three-band waveforms).
//
// Each function repeats the per-frame CPU work of the allshader renderer it
// stands for (pinned Mixxx 3ebac449): the per-pixel-column max over the
// column's visual frames and the vertex (and colour) arrays it hands to GL.
// It does not draw: GPU cost is estimated from the vertex count, the bytes
// uploaded per frame and the pixels filled, which the program prints.
// Synthetic data (seeded random bytes); the loops do not depend on the values.
//
// Build and run:  c++ -O2 -std=c++17 waveform-three-band-bench.cpp -o bench && ./bench
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <random>
#include <vector>

struct Datum { unsigned char low, mid, high, all; };

constexpr int kWidth = 708, kHeight = 128;
constexpr double kFramesPerPixel = 4.0;
constexpr float kHalf = kHeight / 2.0f, kGain = 0.8f;

struct Out {
    std::vector<float> pos, col;
    long fill = 0;
    void clear() { pos.clear(); col.clear(); fill = 0; }
    void rect(float x0, float y0, float x1, float y1) {
        const float v[12] = {x0, y0, x1, y0, x0, y1, x1, y0, x0, y1, x1, y1};
        pos.insert(pos.end(), v, v + 12);
        fill += std::lround(std::fabs(y1 - y0));
    }
    void colour(float r, float g, float b) {
        for (int i = 0; i < 6; i++) { col.push_back(r); col.push_back(g); col.push_back(b); }
    }
};

template <typename F>
void columns(const std::vector<Datum>& data, double first, F&& f) {
    const int size = static_cast<int>(data.size());
    double x = first;
    for (int pos = 0; pos < kWidth; ++pos, x += kFramesPerPixel) {
        const int start = std::max<int>(std::lround(x - kFramesPerPixel / 2) * 2, 0);
        const int stop = std::min<int>(std::max<long>(std::lround(x + kFramesPerPixel / 2),
                                               std::lround(x - kFramesPerPixel / 2) + 1) * 2, size - 1);
        unsigned char m[4][2] = {};
        for (int chn = 0; chn < 2; chn++) {
            for (int i = start + chn; i < stop + chn; i += 2) {
                m[0][chn] = std::max(m[0][chn], data[i].low);
                m[1][chn] = std::max(m[1][chn], data[i].mid);
                m[2][chn] = std::max(m[2][chn], data[i].high);
                m[3][chn] = std::max(m[3][chn], data[i].all);
            }
        }
        f(static_cast<float>(pos), m);
    }
}

const float kLow[3] = {0.357f, 0.584f, 0.831f}, kMid[3] = {0.839f, 0.471f, 0.290f}, kHigh[3] = {0.894f, 0.906f, 0.925f};

void rgb(const std::vector<Datum>& d, double first, Out& o) {  // today, type 17
    const float hf = kGain * kHalf / 255.f;
    o.rect(0, kHalf - .5f, kWidth, kHalf + .5f); o.colour(1, 1, 1);
    columns(d, first, [&](float x, unsigned char (&m)[4][2]) {
        const float l = std::max(m[0][0], m[0][1]), mi = std::max(m[1][0], m[1][1]), h = std::max(m[2][0], m[2][1]);
        float r = l * 1 + mi * 0 + h * 0, g = l * 0 + mi * 1 + h * 0, b = l * 0 + mi * 0 + h * 1;
        const float sum = l * l + mi * mi + h * h;
        float a0 = m[3][0], a1 = m[3][1];
        if (sum != 0.f) { const float f = std::sqrt(sum / sum); a0 *= f; a1 *= f; }
        const float mx = std::max({r, g, b});
        if (mx > 0) { r /= mx; g /= mx; b /= mx; }
        o.rect(x - .5f, kHalf - hf * a0, x + .5f, kHalf + hf * a1);
        o.colour(r, g, b);
    });
}

void filtered(const std::vector<Datum>& d, double first, Out& o) {  // A, type 19 (three uniform-colour draws)
    const float hf = kGain * kHalf / 255.f;
    static Out band[3];  // reused across frames, like the renderers' member arrays
    for (auto& b : band) b.clear();
    columns(d, first, [&](float x, unsigned char (&m)[4][2]) {
        for (int b = 0; b < 3; b++) band[b].rect(x - .5f, kHalf - hf * m[b][0], x + .5f, kHalf + hf * m[b][1]);
    });
    for (auto& b : band) { o.pos.insert(o.pos.end(), b.pos.begin(), b.pos.end()); o.fill += b.fill; }
    o.rect(0, kHalf - .5f, kWidth, kHalf + .5f);
}

void stack(const std::vector<Datum>& d, double first, Out& o) {  // B: painter's order, uniform colours
    const float hf = kGain * kHalf / 255.f;
    static Out layer[3];  // high (whole outline), then mid + low, then low; reused
    for (auto& b : layer) b.clear();
    columns(d, first, [&](float x, unsigned char (&m)[4][2]) {
        float edge[3][2];
        for (int c = 0; c < 2; c++) {
            const float s = float(m[0][c]) + m[1][c] + m[2][c];
            const float t = hf * m[3][c];
            edge[0][c] = t;
            edge[1][c] = s > 0 ? t * (m[0][c] + m[1][c]) / s : 0;
            edge[2][c] = s > 0 ? t * m[0][c] / s : 0;
        }
        for (int k = 0; k < 3; k++) layer[k].rect(x - .5f, kHalf - edge[k][0], x + .5f, kHalf + edge[k][1]);
    });
    for (auto& b : layer) { o.pos.insert(o.pos.end(), b.pos.begin(), b.pos.end()); o.fill += b.fill; }
}

void split(const std::vector<Datum>& d, double first, Out& o) {  // C: per-vertex colour (sorted below the axis)
    const float hf = kGain * kHalf / 255.f;
    o.rect(0, kHalf - .5f, kWidth, kHalf + .5f); o.colour(1, 1, 1);
    columns(d, first, [&](float x, unsigned char (&m)[4][2]) {
        const float l = std::max(m[0][0], m[0][1]), mi = std::max(m[1][0], m[1][1]), h = std::max(m[2][0], m[2][1]);
        o.rect(x - .5f, kHalf - hf * l, x + .5f, kHalf); o.colour(kLow[0], kLow[1], kLow[2]);
        const bool midFirst = mi >= h;
        const float a = midFirst ? mi : h, b = midFirst ? h : mi;
        const float* ca = midFirst ? kMid : kHigh; const float* cb = midFirst ? kHigh : kMid;
        o.rect(x - .5f, kHalf, x + .5f, kHalf + hf * a); o.colour(ca[0], ca[1], ca[2]);
        o.rect(x - .5f, kHalf, x + .5f, kHalf + hf * b); o.colour(cb[0], cb[1], cb[2]);
    });
}

void splitUniform(const std::vector<Datum>& d, double first, Out& o) {  // C as four uniform-colour passes
    // low above the axis; below it: mid where mid >= high, then high everywhere,
    // then mid where mid < high, so the smaller of the two is always in front.
    const float hf = kGain * kHalf / 255.f;
    static Out pass[4];
    for (auto& b : pass) b.clear();
    columns(d, first, [&](float x, unsigned char (&m)[4][2]) {
        const float l = std::max(m[0][0], m[0][1]), mi = std::max(m[1][0], m[1][1]), h = std::max(m[2][0], m[2][1]);
        pass[0].rect(x - .5f, kHalf - hf * l, x + .5f, kHalf);
        pass[mi >= h ? 1 : 3].rect(x - .5f, kHalf, x + .5f, kHalf + hf * mi);
        pass[2].rect(x - .5f, kHalf, x + .5f, kHalf + hf * h);
    });
    for (auto& b : pass) { o.pos.insert(o.pos.end(), b.pos.begin(), b.pos.end()); o.fill += b.fill; }
    o.rect(0, kHalf - .5f, kWidth, kHalf + .5f);
}

void lanes(const std::vector<Datum>& d, double first, Out& o) {  // D: three uniform-colour draws
    const float lane = (kHeight - 4) / 3.f, hf = kGain * lane / 255.f;
    static Out band[3];  // reused across frames, like the renderers' member arrays
    for (auto& b : band) b.clear();
    columns(d, first, [&](float x, unsigned char (&m)[4][2]) {
        for (int b = 0; b < 3; b++) {
            const float floor = (2 - b) * (lane + 2) + lane;
            band[b].rect(x - .5f, floor - hf * std::max(m[b][0], m[b][1]), x + .5f, floor);
        }
    });
    for (auto& b : band) { o.pos.insert(o.pos.end(), b.pos.begin(), b.pos.end()); o.fill += b.fill; }
}

int main() {
    std::mt19937 rng(7);
    std::vector<Datum> data(2 * 441 * 240);  // four minutes, stereo
    for (auto& v : data) { v = {Datum{(unsigned char)(rng() % 200), (unsigned char)(rng() % 140), (unsigned char)(rng() % 150), (unsigned char)(rng() % 255)}}; }
    struct Style { const char* name; void (*fn)(const std::vector<Datum>&, double, Out&); };
    const Style styles[] = {{"today RGB (17)", rgb}, {"A overlay (19)", filtered}, {"B stack", stack}, {"C split", split}, {"C split uniform", splitUniform}, {"D lanes", lanes}};
    std::printf("%-16s %9s %9s %10s %9s %10s\n", "style", "us/frame", "x today", "vertices", "KB/frame", "px filled");
    double base = 0;
    for (const auto& s : styles) {
        Out o;
        const int frames = 20000;
        double first = 1000;
        volatile float sink = 0;
        auto t0 = std::chrono::steady_clock::now();
        for (int i = 0; i < frames; i++) {
            o.clear();
            s.fn(data, first, o);
            sink = sink + o.pos.back();
            first += 14.7;  // 441 frames/s at 30 fps
            if (first > data.size() / 2 - 4000) first = 1000;
        }
        const double us = std::chrono::duration<double, std::micro>(std::chrono::steady_clock::now() - t0).count() / frames;
        if (base == 0) base = us;
        const double kb = (o.pos.size() + o.col.size()) * sizeof(float) / 1024.0;
        std::printf("%-16s %9.1f %9.2f %10zu %9.1f %10ld\n", s.name, us, us / base, o.pos.size() / 2, kb, o.fill);
    }
}
