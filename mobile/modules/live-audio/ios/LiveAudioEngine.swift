import AVFoundation
import Foundation

// AVAudioEngine with Apple's voice processing (echo cancellation and noise
// suppression), the same set-up FaceTime-style calls use, so the tutor's voice
// on the loudspeaker isn't heard as the learner talking over it.
// Based on @speechmatics/expo-two-way-audio (MIT), trimmed down, with a
// 24 kHz player and clear() for interruptions.
final class LiveAudioEngine {
  private let engine = AVAudioEngine()
  private let player = AVAudioPlayerNode()
  private let micFormat: AVAudioFormat
  private let speechFormat: AVAudioFormat
  private var muted = false
  private var running = false
  private var lastLevelAt = Date.distantPast
  private var observers: [NSObjectProtocol] = []

  var onMic: ((Data) -> Void)?
  var onLevel: ((String, Float) -> Void)?

  enum Failure: Error {
    case format
  }

  init() throws {
    guard
      let mic = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: 16000, channels: 1, interleaved: false),
      let speech = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: 24000, channels: 1, interleaved: false)
    else {
      throw Failure.format
    }
    micFormat = mic
    speechFormat = speech
  }

  func start() throws {
    let session = AVAudioSession.sharedInstance()
    try session.setCategory(.playAndRecord, mode: .voiceChat, options: [.defaultToSpeaker, .allowBluetooth])
    try session.setActive(true)

    let input = engine.inputNode
    try input.setVoiceProcessingEnabled(true)
    engine.attach(player)
    engine.connect(player, to: engine.mainMixerNode, format: speechFormat)

    // The tap gets the hardware format; convert to 16 kHz mono for Gemini.
    let hardware = input.outputFormat(forBus: 0)
    guard let converter = AVAudioConverter(from: hardware, to: micFormat) else {
      throw Failure.format
    }
    input.installTap(onBus: 0, bufferSize: 1024, format: hardware) { [weak self] buffer, _ in
      self?.handleMic(buffer, converter: converter)
    }

    observers.append(NotificationCenter.default.addObserver(forName: .AVAudioEngineConfigurationChange, object: engine, queue: .main) { [weak self] _ in
      guard let self = self, self.running, !self.engine.isRunning else { return }
      try? self.engine.start()
    })
    observers.append(NotificationCenter.default.addObserver(forName: AVAudioSession.interruptionNotification, object: session, queue: .main) { [weak self] note in
      guard let self = self, self.running,
            let raw = note.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt,
            AVAudioSession.InterruptionType(rawValue: raw) == .ended else { return }
      try? AVAudioSession.sharedInstance().setActive(true)
      if !self.engine.isRunning { try? self.engine.start() }
    })

    engine.prepare()
    try engine.start()
    player.play()
    running = true
  }

  private func handleMic(_ buffer: AVAudioPCMBuffer, converter: AVAudioConverter) {
    if muted { return }
    let ratio = micFormat.sampleRate / buffer.format.sampleRate
    let capacity = AVAudioFrameCount(Double(buffer.frameLength) * ratio) + 16
    guard let out = AVAudioPCMBuffer(pcmFormat: micFormat, frameCapacity: capacity) else { return }
    var supplied = false
    var error: NSError?
    converter.convert(to: out, error: &error) { _, status in
      if supplied {
        status.pointee = .noDataNow
        return nil
      }
      supplied = true
      status.pointee = .haveData
      return buffer
    }
    guard error == nil, let samples = out.floatChannelData?[0] else { return }
    let count = Int(out.frameLength)
    if count == 0 { return }
    var pcm = [Int16](repeating: 0, count: count)
    var sum: Float = 0
    for i in 0..<count {
      let value = max(-1, min(1, samples[i]))
      pcm[i] = Int16(value * Float(Int16.max))
      sum += value * value
    }
    onMic?(pcm.withUnsafeBufferPointer { Data(buffer: $0) })
    report("you", rms: sqrt(sum / Float(count)))
  }

  func play(_ data: Data) {
    let frames = data.count / 2
    guard running, frames > 0, let buffer = AVAudioPCMBuffer(pcmFormat: speechFormat, frameCapacity: AVAudioFrameCount(frames)) else { return }
    buffer.frameLength = AVAudioFrameCount(frames)
    guard let target = buffer.floatChannelData?[0] else { return }
    var sum: Float = 0
    data.withUnsafeBytes { (raw: UnsafeRawBufferPointer) in
      for i in 0..<frames {
        let value = Float(Int16(littleEndian: raw.loadUnaligned(fromByteOffset: i * 2, as: Int16.self))) / 32768
        target[i] = value
        sum += value * value
      }
    }
    player.scheduleBuffer(buffer, completionHandler: nil)
    if !player.isPlaying { player.play() }
    report("tutor", rms: sqrt(sum / Float(frames)))
  }

  /// Drops speech that hasn't been played yet (the learner talked over the tutor).
  func clear() {
    guard running else { return }
    player.stop()
    player.play()
  }

  func setMuted(_ value: Bool) {
    muted = value
    if value { onLevel?("you", 0) }
  }

  func stop() {
    guard running else { return }
    running = false
    observers.forEach { NotificationCenter.default.removeObserver($0) }
    observers = []
    engine.inputNode.removeTap(onBus: 0)
    player.stop()
    engine.stop()
    try? engine.inputNode.setVoiceProcessingEnabled(false)
    try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
  }

  private func report(_ who: String, rms: Float) {
    // About 20 updates a second is plenty for the picture.
    let now = Date()
    if who == "you" && now.timeIntervalSince(lastLevelAt) < 0.05 { return }
    if who == "you" { lastLevelAt = now }
    let db = 20 * log10(max(rms, 1e-5))
    let level = max(0, min(1, (db + 60) / 60))
    onLevel?(who, level * level)
  }
}
