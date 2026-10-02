// Command fanout is the E2 relay stand-in: one sender pushes a fixed frame at a
// fixed rate to N listeners over TCP, UDP unicast (sendmmsg) or UDP multicast,
// and a receiver process plays the N listeners.
//
//	fanout send -mode tcp   -n 1000 -listen 10.77.0.1:7000
//	fanout send -mode udp   -n 1000 -dst 10.77.0.2 -base 20000
//	fanout send -mode mcast -group 239.255.13.13:9999 -ifaddr 10.77.0.1
//	fanout recv -mode tcp   -n 1000 -connect 10.77.0.1:7000
//	fanout recv -mode udp   -n 1000 -bind 10.77.0.2 -base 20000
//	fanout recv -mode mcast -n 1000 -group 239.255.13.13:9999 -ifaddr 10.77.0.2
//
// The sender prints "ready" once every listener is attached, then a JSON
// summary on exit. Its enqueue_all_* fields time the sender's own loop over
// the N listeners (sender enqueue time), not delivery to them. Only the standard library is used; sendmmsg is called
// through syscall.Syscall6.
package main

import (
	"encoding/binary"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net"
	"os"
	"sort"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
	"unsafe"
)

var (
	mode     = flag.String("mode", "tcp", "tcp | udp | mcast")
	n        = flag.Int("n", 10, "listeners")
	rate     = flag.Float64("rate", 10, "frames per second")
	size     = flag.Int("size", 700, "frame bytes")
	duration = flag.Duration("duration", 40*time.Second, "how long to send / receive")
	listen   = flag.String("listen", "10.77.0.1:7000", "tcp: sender listen address")
	connect  = flag.String("connect", "10.77.0.1:7000", "tcp: receiver dial address")
	dst      = flag.String("dst", "10.77.0.2", "udp: listener address")
	bind     = flag.String("bind", "10.77.0.2", "udp: receiver bind address")
	base     = flag.Int("base", 20000, "udp: first listener port")
	group    = flag.String("group", "239.255.13.13:9999", "mcast group:port")
	ifaddr   = flag.String("ifaddr", "10.77.0.1", "mcast: interface address")
	batch    = flag.Int("batch", 1024, "udp: messages per sendmmsg (UIO_MAXIOV = 1024)")
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: fanout send|recv [flags]")
		os.Exit(2)
	}
	cmd := os.Args[1]
	flag.CommandLine.Parse(os.Args[2:])
	switch cmd {
	case "send":
		send()
	case "recv":
		recv()
	default:
		fmt.Fprintln(os.Stderr, "unknown command", cmd)
		os.Exit(2)
	}
}

// ------------------------------------------------------------------ sender

type sendStats struct {
	Mode        string  `json:"mode"`
	N           int     `json:"n"`
	Frames      int     `json:"frames"`
	Syscalls    int64   `json:"syscalls"`
	Messages    int64   `json:"messages"`
	Bytes       int64   `json:"bytes"`
	Errors      int64   `json:"errors"`
	Short       int64   `json:"short_writes"`
	// Sender enqueue time for one frame to all N listeners: how long the
	// push() loop (write / sendmmsg / sendto) took, on the sender's clock.
	// It is not when the last listener received the frame: there are no
	// receiver timestamps, so arrival spread is not measured.
	EnqueueAllP50us float64 `json:"enqueue_all_p50_us"`
	EnqueueAllP99us float64 `json:"enqueue_all_p99_us"`
	EnqueueAllMaxus float64 `json:"enqueue_all_max_us"`
	Late        int     `json:"late_ticks"`
}

func frame() []byte {
	b := make([]byte, *size)
	for i := range b {
		b[i] = byte(i * 131)
	}
	binary.BigEndian.PutUint16(b, uint16(*size-2)) // tcp framing: 2-byte length prefix
	return b
}

func send() {
	st := sendStats{Mode: *mode, N: *n}
	var push func() // one frame to every listener
	f := frame()
	switch *mode {
	case "tcp":
		push = tcpSender(f, &st)
	case "udp":
		push = udpSender(f, &st)
	case "mcast":
		push = mcastSender(f, &st)
	default:
		fatal(fmt.Errorf("unknown mode %q", *mode))
	}
	fmt.Println("ready")
	period := time.Duration(float64(time.Second) / *rate)
	deadline := time.Now().Add(*duration)
	enqueue := make([]float64, 0, int(duration.Seconds()**rate)+1) // µs to hand one frame to the kernel for all N
	next := time.Now()
	for time.Now().Before(deadline) {
		t0 := time.Now()
		push()
		enqueue = append(enqueue, float64(time.Since(t0).Microseconds()))
		st.Frames++
		next = next.Add(period)
		if d := time.Until(next); d > 0 {
			time.Sleep(d)
		} else {
			st.Late++
		}
	}
	sort.Float64s(enqueue)
	if len(enqueue) > 0 {
		st.EnqueueAllP50us = enqueue[len(enqueue)/2]
		st.EnqueueAllP99us = enqueue[len(enqueue)*99/100]
		st.EnqueueAllMaxus = enqueue[len(enqueue)-1]
	}
	json.NewEncoder(os.Stdout).Encode(st)
}

func tcpSender(f []byte, st *sendStats) func() {
	ln, err := net.Listen("tcp4", *listen)
	fatal(err)
	conns := make([]*net.TCPConn, 0, *n)
	for len(conns) < *n {
		c, err := ln.Accept()
		fatal(err)
		tc := c.(*net.TCPConn)
		tc.SetNoDelay(true)
		setCubic(tc)
		conns = append(conns, tc)
	}
	return func() {
		for _, c := range conns {
			m, err := c.Write(f)
			st.Syscalls++
			st.Messages++
			st.Bytes += int64(m)
			if err != nil {
				st.Errors++
			} else if m < len(f) {
				st.Short++
			}
		}
	}
}

// setCubic: this host defaults to BBR; use cubic, the upstream default, per socket.
func setCubic(c *net.TCPConn) {
	raw, err := c.SyscallConn()
	fatal(err)
	raw.Control(func(fd uintptr) {
		syscall.SetsockoptString(int(fd), syscall.IPPROTO_TCP, syscall.TCP_CONGESTION, "cubic")
	})
}

// mmsghdr is struct mmsghdr from <sys/socket.h> on linux/amd64.
type mmsghdr struct {
	hdr syscall.Msghdr
	len uint32
	_   [4]byte
}

func udpSender(f []byte, st *sendStats) func() {
	fd, err := syscall.Socket(syscall.AF_INET, syscall.SOCK_DGRAM, 0)
	fatal(err)
	fatal(syscall.SetsockoptInt(fd, syscall.SOL_SOCKET, syscall.SO_SNDBUF, 4<<20))
	ip := net.ParseIP(*dst).To4()
	addrs := make([]syscall.RawSockaddrInet4, *n)
	iov := syscall.Iovec{Base: &f[0]}
	iov.SetLen(len(f))
	msgs := make([]mmsghdr, *n)
	for i := range addrs {
		addrs[i].Family = syscall.AF_INET
		port := uint16(*base + i)
		addrs[i].Port = port<<8 | port>>8 // network byte order
		copy(addrs[i].Addr[:], ip)
		msgs[i].hdr.Name = (*byte)(unsafe.Pointer(&addrs[i]))
		msgs[i].hdr.Namelen = syscall.SizeofSockaddrInet4
		msgs[i].hdr.Iov = &iov
		msgs[i].hdr.Iovlen = 1
	}
	return func() {
		for off := 0; off < len(msgs); {
			k := len(msgs) - off
			if k > *batch {
				k = *batch
			}
			r, _, e := syscall.Syscall6(307 /* SYS_SENDMMSG */, uintptr(fd), uintptr(unsafe.Pointer(&msgs[off])),
				uintptr(k), 0, 0, 0)
			st.Syscalls++
			if e != 0 {
				st.Errors++
				off += k
				continue
			}
			st.Messages += int64(r)
			st.Bytes += int64(r) * int64(len(f))
			off += int(r)
		}
	}
}

func mcastSender(f []byte, st *sendStats) func() {
	fd, err := syscall.Socket(syscall.AF_INET, syscall.SOCK_DGRAM, 0)
	fatal(err)
	var ifa [4]byte
	copy(ifa[:], net.ParseIP(*ifaddr).To4())
	fatal(syscall.SetsockoptInet4Addr(fd, syscall.IPPROTO_IP, syscall.IP_MULTICAST_IF, ifa))
	fatal(syscall.SetsockoptInt(fd, syscall.IPPROTO_IP, syscall.IP_MULTICAST_TTL, 1))
	fatal(syscall.SetsockoptInt(fd, syscall.IPPROTO_IP, syscall.IP_MULTICAST_LOOP, 0))
	ga, err := net.ResolveUDPAddr("udp4", *group)
	fatal(err)
	sa := &syscall.SockaddrInet4{Port: ga.Port}
	copy(sa.Addr[:], ga.IP.To4())
	return func() {
		err := syscall.Sendto(fd, f, 0, sa)
		st.Syscalls++
		if err != nil {
			st.Errors++
			return
		}
		st.Messages++
		st.Bytes += int64(len(f))
	}
}

// ------------------------------------------------------------------ receivers

type recvStats struct {
	Mode      string `json:"mode"`
	N         int    `json:"n"`
	Attached  int64  `json:"attached"`
	MinFrames int64  `json:"min_frames"`
	MaxFrames int64  `json:"max_frames"`
	Frames    int64  `json:"frames"`
	Bytes     int64  `json:"bytes"`
	Errors    int64  `json:"errors"`
}

func recv() {
	counts := make([]int64, *n)
	var bytes, errs, attached atomic.Int64
	var wg sync.WaitGroup
	stop := time.Now().Add(*duration)
	reader := func(i int, rd func([]byte) (int, error), closer io.Closer) {
		defer wg.Done()
		buf := make([]byte, 2048)
		for {
			m, err := rd(buf)
			if err != nil {
				// EOF when the sender exits, or a closed socket at our own deadline, is the normal end
				if err != io.EOF && err != io.ErrUnexpectedEOF && time.Now().Before(stop) {
					errs.Add(1)
				}
				return
			}
			atomic.AddInt64(&counts[i], 1)
			bytes.Add(int64(m))
		}
	}
	var closers []io.Closer
	var mu sync.Mutex
	sem := make(chan struct{}, 256) // bounded connect concurrency
	for i := 0; i < *n; i++ {
		wg.Add(1)
		switch *mode {
		case "tcp":
			sem <- struct{}{}
			go func(i int) {
				c, err := net.Dial("tcp4", *connect)
				<-sem
				if err != nil {
					errs.Add(1)
					wg.Done()
					return
				}
				attached.Add(1)
				mu.Lock()
				closers = append(closers, c)
				mu.Unlock()
				reader(i, func(b []byte) (int, error) { return io.ReadFull(c, b[:*size]) }, c)
			}(i)
		case "udp":
			c, err := net.ListenUDP("udp4", &net.UDPAddr{IP: net.ParseIP(*bind), Port: *base + i})
			fatal(err)
			c.SetReadBuffer(1 << 20)
			attached.Add(1)
			closers = append(closers, c)
			go reader(i, func(b []byte) (int, error) { return c.Read(b) }, c)
		case "mcast":
			c := mcastSocket()
			attached.Add(1)
			closers = append(closers, c)
			go reader(i, func(b []byte) (int, error) { return c.Read(b) }, c)
		}
	}
	fmt.Println("attached")
	done := make(chan struct{})
	go func() { wg.Wait(); close(done) }()
	select { // TCP readers all end at EOF when the sender exits; UDP readers end at the deadline
	case <-done:
	case <-time.After(time.Until(stop)):
	}
	mu.Lock()
	for _, c := range closers {
		c.Close()
	}
	mu.Unlock()
	wg.Wait()
	rs := recvStats{Mode: *mode, N: *n, Attached: attached.Load(), Bytes: bytes.Load(), Errors: errs.Load(),
		MinFrames: -1}
	for _, c := range counts {
		rs.Frames += c
		if rs.MinFrames < 0 || c < rs.MinFrames {
			rs.MinFrames = c
		}
		if c > rs.MaxFrames {
			rs.MaxFrames = c
		}
	}
	json.NewEncoder(os.Stdout).Encode(rs)
}

// mcastSocket: one socket bound to the group port (SO_REUSEADDR) and joined on ifaddr.
func mcastSocket() *os.File {
	ga, err := net.ResolveUDPAddr("udp4", *group)
	fatal(err)
	fd, err := syscall.Socket(syscall.AF_INET, syscall.SOCK_DGRAM, 0)
	fatal(err)
	fatal(syscall.SetsockoptInt(fd, syscall.SOL_SOCKET, syscall.SO_REUSEADDR, 1))
	fatal(syscall.SetsockoptInt(fd, syscall.SOL_SOCKET, syscall.SO_RCVBUF, 1<<20))
	sa := &syscall.SockaddrInet4{Port: ga.Port}
	copy(sa.Addr[:], ga.IP.To4())
	fatal(syscall.Bind(fd, sa))
	mreq := &syscall.IPMreq{}
	copy(mreq.Multiaddr[:], ga.IP.To4())
	copy(mreq.Interface[:], net.ParseIP(*ifaddr).To4())
	fatal(syscall.SetsockoptIPMreq(fd, syscall.IPPROTO_IP, syscall.IP_ADD_MEMBERSHIP, mreq))
	fatal(syscall.SetNonblock(fd, true))
	return os.NewFile(uintptr(fd), "mcast") // non-blocking: reads go through Go's poller
}

func fatal(err error) {
	if err != nil {
		fmt.Fprintln(os.Stderr, "fanout:", err)
		os.Exit(1)
	}
}
