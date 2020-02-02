import { async, ComponentFixture, TestBed } from '@angular/core/testing'

import { LogBoxComponent } from './log-box.component'

describe('LogBoxComponent', () => {
    let component: LogBoxComponent
    let fixture: ComponentFixture<LogBoxComponent>

    beforeEach(async(() => {
        TestBed.configureTestingModule({
            declarations: [LogBoxComponent],
        }).compileComponents()
    }))

    beforeEach(() => {
        fixture = TestBed.createComponent(LogBoxComponent)
        component = fixture.componentInstance
        fixture.detectChanges()
    })

    it('should create', () => {
        expect(component).toBeTruthy()
    })
})
