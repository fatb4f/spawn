## Main alternatives to AppArmor for runtime guardrails

### 1. **SELinux**

Use this when you want **stronger, label-based MAC** and are willing to accept more policy complexity. SELinux is a Mandatory Access Control system where processes and system resources have security labels/contexts, and policy defines which interactions are allowed. ([Red Hat Docs][1])

### 2. **Landlock**

Use this when you want **self-imposed, scoped sandboxing from user space**, especially for unprivileged processes. Landlock is a **stackable LSM** that lets even unprivileged processes restrict their own ambient rights, including filesystem access and, in newer ABIs, network rules. ([Linux Kernel Documentation][2])

### 3. **seccomp**

Use this when you want to **reduce kernel attack surface** by filtering syscalls and syscall arguments. The kernel docs are explicit that seccomp is **not a complete sandbox** by itself; it is a building block that should be combined with other controls such as an LSM. ([Linux Kernel Documentation][3])

### 4. **systemd sandboxing + capability dropping**

Use this when your executor already runs as a **systemd unit**. `systemd.exec(5)` exposes sandboxing, system-call filtering, mount/filesystem isolation, namespace-related options, and capability controls for service processes. Linux capabilities also let you split traditional root privilege into smaller per-thread units and drop what is not needed. ([man7.org][4])

### 5. **cgroups v2**

Use this when the guardrail is partly about **resource and blast-radius control** rather than access control alone. cgroup v2 organizes processes hierarchically and lets controllers distribute and limit system resources in a controlled way. ([Linux Kernel Documentation][5])

### 6. **gVisor**

Use this when you want a **stronger isolation boundary for containers** without going all the way to full traditional VMs. gVisor inserts a userspace application kernel between the workload and the host kernel, reducing container-escape risk while remaining compatible with OCI-style tooling. ([gVisor][6])

### 7. **Kata Containers / microVM isolation**

Use this for **higher-risk workloads** where hardware-virtualization-style isolation is worth the overhead. Kata Containers emphasizes lightweight-VM isolation for container workloads, and Firecracker provides lightweight **microVMs** aimed at stronger workload isolation than standard containers. ([Kata Containers][7])

### 8. **eBPF-based runtime enforcement (Tetragon)**

Use this when you want **kernel-level runtime policy with fast, event-driven enforcement**. Tetragon can monitor kernel events and also enforce restrictions at kernel level, including actions like killing a process on violation; its policies can be scoped with Kubernetes-aware filters. ([Tetragon][8])

### 9. **Runtime detection and response (Falco)**

Use this when you want **behavioral guardrails and alerting**. Falco monitors runtime events, evaluates them against rules, and emits alerts; it is stronger as a detect/respond layer than as a hard prevention primitive. ([Falco][9])

---

## How these fit by layer

For your architecture, the options break down cleanly:

* **Access confinement:** AppArmor, SELinux, Landlock. ([Ubuntu][10])
* **Kernel surface reduction:** seccomp, capability dropping. ([Linux Kernel Documentation][3])
* **Service/process sandboxing:** systemd sandboxing, namespaces, cgroups. ([man7.org][4])
* **Stronger workload isolation:** gVisor, Kata, Firecracker. ([gVisor][6])
* **Behavioral runtime enforcement/detection:** Tetragon, Falco. ([Tetragon][8])

---

## Best candidates for your daemonized agent-loop design

Given your **plan-promotion gate + OPA/Rego + state-space** model, the most natural runtime guardrail combinations are:

### **Option A: Linux-native, low overhead**

* OPA/Rego for plan admission
* systemd sandboxing
* seccomp
* dropped Linux capabilities
* AppArmor or SELinux for MAC
* Falco or Tetragon for runtime visibility/response
  This is the best fit when the executor is a service on a host you control. ([man7.org][4])

### **Option B: Self-restricting executor**

* OPA/Rego for plan admission
* Landlock in the executor process
* seccomp
* capabilities dropped to minimum
  This is attractive when you want the executor to **confine itself** even without broad system policy changes. ([Linux Kernel Documentation][2])

### **Option C: High-risk action isolation**

* OPA/Rego for plan admission
* run the actual executor in gVisor, Kata, or Firecracker
* add seccomp/MAC inside or around that runtime
* Tetragon or Falco for runtime observation
  This is the strongest model when the promoted plan may run semi-trusted or dynamically generated code. ([gVisor][6])

---

## The practical rule

No single control is enough:

* **OPA/Rego** decides whether the action should run.
* **MAC / sandbox / syscall filters** constrain what it can do if it runs.
* **resource controls** limit damage.
* **runtime detection/enforcement** catches drift or violations during execution. ([Linux Kernel Documentation][3])

## My default recommendation for your case

For a userspace-aware policy daemon, the most balanced stack is:

**OPA/Rego + systemd sandboxing + seccomp + dropped capabilities + AppArmor or SELinux + Tetragon/Falco**, and then reserve **gVisor/Kata/Firecracker** for the subset of plans that are highest risk. ([man7.org][4])

I can turn this into a control matrix next: **which guardrails belong at plan gate, unit level, executor level, and observation level**.

[1]: https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/using_selinux/getting-started-with-selinux_using-selinux?utm_source=chatgpt.com "Chapter 1. Getting started with SELinux"
[2]: https://docs.kernel.org/userspace-api/landlock.html "Landlock: unprivileged access control — The Linux Kernel  documentation"
[3]: https://docs.kernel.org/userspace-api/seccomp_filter.html "Seccomp BPF (SECure COMPuting with filters) — The Linux Kernel  documentation"
[4]: https://man7.org/linux/man-pages/man5/systemd.exec.5.html?utm_source=chatgpt.com "systemd.exec(5) - Linux manual page"
[5]: https://docs.kernel.org/admin-guide/cgroup-v2.html "Control Group v2 — The Linux Kernel  documentation"
[6]: https://gvisor.dev/docs/ " What is gVisor? - gVisor"
[7]: https://katacontainers.io/blog/kata-containers-agent-sandbox-integration/?utm_source=chatgpt.com "What's to Expect from Agent Sandbox"
[8]: https://tetragon.io/docs/getting-started/enforcement/ "Policy Enforcement | Tetragon - eBPF-based Security Observability and Runtime Enforcement"
[9]: https://falco.org/docs/ "The Falco Project | Falco"
[10]: https://ubuntu.com/tutorials/beginning-apparmor-profile-development?utm_source=chatgpt.com "AppArmor - Ubuntu security documentation"

